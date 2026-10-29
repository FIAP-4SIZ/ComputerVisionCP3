#pragma once
#include "../src/protocol.h"
#include <stdexcept>
#include <string>
inline void check(bool value,const char* message) { if (!value) throw std::runtime_error(message); }
inline void put_float(unsigned char* data,float value) {
    std::uint32_t n; std::memcpy(&n,&value,4); mpvr::put32(data,n);
}
inline std::array<unsigned char,mpvr::packet_size> packet(unsigned side=0,unsigned sequence=1,bool valid=true) {
    std::array<unsigned char,mpvr::packet_size> bytes{};
    std::memcpy(bytes.data(),"MPVRH001",8); mpvr::put32(bytes.data()+8,side);
    mpvr::put32(bytes.data()+12,sequence); mpvr::put32(bytes.data()+16,valid?1u:0u);
    put_float(bytes.data()+32,1.f);
    for (unsigned i=0;i<mpvr::bone_count;++i) put_float(bytes.data()+60+i*28,1.f);
    return bytes;
}
