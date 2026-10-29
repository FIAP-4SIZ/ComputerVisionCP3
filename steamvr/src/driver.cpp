// Adaptador OpenVR: não executa visão nem falsifica um modelo Index/Touch.
#include "receiver.h"
#include <openvr_driver.h>
#include <atomic>
#include <chrono>
#include <mutex>
#include <string>

namespace {
double seconds() {
    return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
}
vr::DriverPose_t invalid_pose() {
    vr::DriverPose_t pose{};
    pose.qRotation.w=pose.qWorldFromDriverRotation.w=pose.qDriverFromHeadRotation.w=1;
    pose.result=vr::TrackingResult_Running_OutOfRange;
    pose.deviceIsConnected=true;
    return pose;
}
class Hand final:public vr::ITrackedDeviceServerDriver {
    const unsigned side_;
    std::atomic<std::uint32_t> id_{vr::k_unTrackedDeviceIndexInvalid};
    vr::VRInputComponentHandle_t skeleton_=0, trigger_=0, trigger_value_=0, system_=0;
    std::mutex mutex_;
    vr::DriverPose_t pose_=invalid_pose();
public:
    explicit Hand(unsigned side):side_(side) {}
    vr::EVRInitError Activate(std::uint32_t id) override {
        const auto container=vr::VRProperties()->TrackedDeviceToPropertyContainer(id);
        auto* properties=vr::VRProperties();
        properties->SetStringProperty(container,vr::Prop_ManufacturerName_String,"FIAP MediaPipe (experimental)");
        properties->SetStringProperty(container,vr::Prop_ModelNumber_String,"MediaPipe optical hand");
        properties->SetStringProperty(container,vr::Prop_TrackingSystemName_String,"MediaPipe webcam");
        properties->SetStringProperty(container,vr::Prop_ControllerType_String,"fiap_mediapipe_hand");
        properties->SetStringProperty(container,vr::Prop_InputProfilePath_String,"{mediapipe_hands}/input/mediapipe_hand_profile.json");
        properties->SetInt32Property(container,vr::Prop_ControllerRoleHint_Int32,
            side_==0?vr::TrackedControllerRole_LeftHand:vr::TrackedControllerRole_RightHand);
        auto* input=vr::VRDriverInput();
        const auto error=input->CreateSkeletonComponent(container,
            side_==0?"/input/skeleton/left":"/input/skeleton/right",
            side_==0?"/skeleton/hand/left":"/skeleton/hand/right",
            "/pose/raw",vr::VRSkeletalTracking_Full,nullptr,0,&skeleton_);
        if (error!=vr::VRInputError_None ||
            input->CreateBooleanComponent(container,"/input/trigger/click",&trigger_)!=vr::VRInputError_None ||
            input->CreateScalarComponent(container,"/input/trigger/value",&trigger_value_,vr::VRScalarType_Absolute,vr::VRScalarUnits_NormalizedOneSided)!=vr::VRInputError_None ||
            input->CreateBooleanComponent(container,"/input/system/click",&system_)!=vr::VRInputError_None) {
            vr::VRDriverLog()->Log("MediaPipe: failed to create hand input components");
            return vr::VRInitError_Driver_Failed;
        }
        // Obrigatório na inicialização da API; a pose permanece INVÁLIDA até
        // chegar uma mão observada. Estes zeros não são medições publicadas.
        vr::VRBoneTransform_t initial[mpvr::bone_count]{};
        for (auto& bone:initial) { bone.position.v[3]=1; bone.orientation.w=1; }
        input->UpdateSkeletonComponent(skeleton_,vr::VRSkeletalMotionRange_WithoutController,initial,mpvr::bone_count);
        input->UpdateSkeletonComponent(skeleton_,vr::VRSkeletalMotionRange_WithController,initial,mpvr::bone_count);
        id_=id;
        return vr::VRInitError_None;
    }
    void Deactivate() override { id_=vr::k_unTrackedDeviceIndexInvalid; }
    void EnterStandby() override {}
    void* GetComponent(const char*) override { return nullptr; }
    void DebugRequest(const char*,char* response,std::uint32_t size) override { if (size) response[0]='\0'; }
    vr::DriverPose_t GetPose() override { std::lock_guard<std::mutex> lock(mutex_); return pose_; }
    void update(const mpvr::State& state,const mpvr::Control& control,double now,const vr::TrackedDevicePose_t& head) {
        const auto id=id_.load();
        if (id==vr::k_unTrackedDeviceIndexInvalid) return;
        auto pose=invalid_pose();
        const bool valid=state.live(now) && head.bPoseIsValid && head.bDeviceIsConnected;
        if (valid) {
            pose.poseIsValid=true; pose.result=vr::TrackingResult_Running_OK;
            const auto& source=state.frame;
            pose.qRotation={source.pose.rotation[0],source.pose.rotation[1],source.pose.rotation[2],source.pose.rotation[3]};
            for (unsigned i=0;i<3;++i) {
                pose.vecPosition[i]=source.pose.position[i];
                // As posições Python são relativas à cabeça. Origem real é
                // lida do HMD ativo, inclusive quando é o driver null oficial.
                pose.vecWorldFromDriverTranslation[i]=head.mDeviceToAbsoluteTracking.m[i][3];
            }
            vr::VRBoneTransform_t bones[mpvr::bone_count]{};
            for (unsigned i=0;i<mpvr::bone_count;++i) {
                const auto& source_bone=source.bones[i];
                for (unsigned axis=0;axis<3;++axis) bones[i].position.v[axis]=source_bone.position[axis];
                bones[i].position.v[3]=1;
                bones[i].orientation={source_bone.rotation[0],source_bone.rotation[1],source_bone.rotation[2],source_bone.rotation[3]};
            }
            vr::VRDriverInput()->UpdateSkeletonComponent(skeleton_,vr::VRSkeletalMotionRange_WithoutController,bones,mpvr::bone_count);
            vr::VRDriverInput()->UpdateSkeletonComponent(skeleton_,vr::VRSkeletalMotionRange_WithController,bones,mpvr::bone_count);
        }
        // Comandos explícitos, nunca gestos invisíveis associados aos dedos.
        const bool pressed=control.pressed(now,valid);
        vr::VRDriverInput()->UpdateBooleanComponent(trigger_,pressed,0);
        vr::VRDriverInput()->UpdateScalarComponent(trigger_value_,pressed?1.f:0.f,0);
        vr::VRDriverInput()->UpdateBooleanComponent(system_,false,0);
        {
            std::lock_guard<std::mutex> lock(mutex_); pose_=pose;
        }
        vr::VRServerDriverHost()->TrackedDevicePoseUpdated(id,pose,sizeof(pose));
    }
};
class Provider final:public vr::IServerTrackedDeviceProvider {
    mpvr::Receiver receiver_;
    Hand left_{0},right_{1};
public:
    vr::EVRInitError Init(vr::IVRDriverContext* context) override {
        VR_INIT_SERVER_DRIVER_CONTEXT(context);
        if (!receiver_.open()) {
            vr::VRDriverLog()->Log("MediaPipe: cannot bind 127.0.0.1:39570 (another instance?)");
            return vr::VRInitError_Driver_Failed;
        }
        if (!vr::VRServerDriverHost()->TrackedDeviceAdded("FIAP_MP_Left",vr::TrackedDeviceClass_Controller,&left_) ||
            !vr::VRServerDriverHost()->TrackedDeviceAdded("FIAP_MP_Right",vr::TrackedDeviceClass_Controller,&right_)) {
            receiver_.close(); return vr::VRInitError_Driver_Failed;
        }
        vr::VRDriverLog()->Log("MediaPipe hand driver v1 ready on loopback UDP 39570");
        return vr::VRInitError_None;
    }
    void Cleanup() override { receiver_.close(); VR_CLEANUP_SERVER_DRIVER_CONTEXT(); }
    const char* const* GetInterfaceVersions() override { return vr::k_InterfaceVersions; }
    void RunFrame() override {
        vr::TrackedDevicePose_t head{};
        vr::VRServerDriverHost()->GetRawTrackedDevicePoses(0,&head,1);
        const double now=seconds();
        receiver_.poll(now,head.bPoseIsValid && head.bDeviceIsConnected);
        left_.update(receiver_.hands[0],receiver_.control,now,head);
        right_.update(receiver_.hands[1],receiver_.control,now,head);
    }
    bool ShouldBlockStandbyMode() override { return false; }
    void EnterStandby() override {}
    void LeaveStandby() override {}
};
Provider provider;
}
#ifdef _WIN32
#define MPVR_EXPORT extern "C" __declspec(dllexport)
#else
#define MPVR_EXPORT extern "C" __attribute__((visibility("default")))
#endif
MPVR_EXPORT void* HmdDriverFactory(const char* name,int* error) {
    if (name && std::strcmp(name,vr::IServerTrackedDeviceProvider_Version)==0) {
        if (error) *error=vr::VRInitError_None;
        return &provider;
    }
    if (error) *error=vr::VRInitError_Init_InterfaceNotFound;
    return nullptr;
}
