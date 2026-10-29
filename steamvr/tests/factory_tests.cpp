#include <openvr_driver.h>
#include "test_helpers.h"
extern "C" void* HmdDriverFactory(const char*,int*);
int main() {
    int error=0;
    check(HmdDriverFactory("unsupported",&error)==nullptr && error==vr::VRInitError_Init_InterfaceNotFound,"unknown interface rejected");
    check(HmdDriverFactory(nullptr,nullptr)==nullptr,"null interface rejected");
    auto* provider=static_cast<vr::IServerTrackedDeviceProvider*>(HmdDriverFactory(vr::IServerTrackedDeviceProvider_Version,&error));
    check(provider!=nullptr && error==0,"real shared library factory");
    check(provider->GetInterfaceVersions()!=nullptr && !provider->ShouldBlockStandbyMode(),"provider ABI accessible without SteamVR");
}
