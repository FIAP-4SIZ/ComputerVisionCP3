// Protocolo local, independente de alinhamento de structs e do SDK OpenVR.
#pragma once
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <cstddef>

namespace mpvr {
constexpr std::uint32_t bone_count = 31;
constexpr std::size_t packet_size = 20 + (7 + bone_count * 7) * 4;
constexpr double timeout = .5;
struct Transform { std::array<float, 3> position{}; std::array<float, 4> rotation{1,0,0,0}; };
struct Frame { std::uint32_t side=0, sequence=0; bool valid=false; Transform pose; std::array<Transform,bone_count> bones{}; };
inline std::uint32_t u32(const unsigned char* p) {
    return std::uint32_t(p[0]) | (std::uint32_t(p[1])<<8) | (std::uint32_t(p[2])<<16) | (std::uint32_t(p[3])<<24);
}
inline void put32(unsigned char* p, std::uint32_t n) {
    for (unsigned i=0;i<4;++i) p[i]=static_cast<unsigned char>((n>>(i*8))&255);
}
inline float number(const unsigned char* p) { const auto n=u32(p); float f; std::memcpy(&f,&n,4); return f; }
inline void put_number(unsigned char* p,float value) { std::uint32_t n; std::memcpy(&n,&value,4); put32(p,n); }
inline bool transform(const unsigned char* p, Transform& out, float limit) {
    for (unsigned i=0;i<3;++i) { out.position[i]=number(p+i*4); if (!std::isfinite(out.position[i]) || std::abs(out.position[i])>limit) return false; }
    double norm=0;
    for (unsigned i=0;i<4;++i) { out.rotation[i]=number(p+12+i*4); if (!std::isfinite(out.rotation[i])) return false; norm+=double(out.rotation[i])*out.rotation[i]; }
    return std::abs(norm-1.) < .002;
}
inline bool decode(const unsigned char* data, std::size_t size, Frame& out) {
    if (size!=packet_size || std::memcmp(data,"MPVRH001",8)!=0) return false;
    Frame frame; frame.side=u32(data+8); frame.sequence=u32(data+12);
    const auto flags=u32(data+16);
    if (frame.side>1 || flags>1) return false;
    frame.valid=flags==1;
    // Invalidar uma mão não requer publicar ossos/posições fictícios.
    if (frame.valid) {
        if (!transform(data+20,frame.pose,10.f)) return false;
        for (unsigned i=0;i<bone_count;++i)
            if (!transform(data+48+i*28,frame.bones[i],1.f)) return false;
        // O root é identidade; posição do dispositivo é a origem da mão.
        for (float v:frame.bones[0].position) if (std::abs(v)>1e-6f) return false;
        const auto& q=frame.bones[0].rotation;
        if (std::abs(std::abs(q[0])-1)>1e-6f || std::abs(q[1])+std::abs(q[2])+std::abs(q[3])>1e-6f) return false;
    }
    out=frame; return true;
}
struct State {
    Frame frame{}; bool received=false; double last=0;
    bool live(double now) const { return received && frame.valid && now>=last && now-last<timeout; }
    bool accept(const Frame& next, double now) {
        if (!std::isfinite(now) || now<0) return false;
        if (received && now-last<timeout) {
            const auto difference=next.sequence-frame.sequence;
            if (difference==0 || difference>=0x80000000u) return false;
        }
        frame=next; received=true; last=now; return true;
    }
};
struct Control {
    double release_at=0;
    bool pulse(double now, std::uint32_t milliseconds) {
        if (!std::isfinite(now) || now<0 || milliseconds>500) return false;
        release_at=now+double(milliseconds)/1000.; return true;
    }
    bool pressed(double now, bool valid) const { return valid && now<release_at; }
};
} // namespace mpvr
