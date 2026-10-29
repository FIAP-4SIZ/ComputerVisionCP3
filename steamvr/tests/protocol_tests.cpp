#include "test_helpers.h"
#include <limits>
#include <iostream>
int main() {
    auto bytes=packet(1,17); mpvr::Frame frame;
    check(mpvr::decode(bytes.data(),bytes.size(),frame),"valid frame");
    check(frame.side==1 && frame.sequence==17 && frame.valid,"header values");
    check(mpvr::packet_size==916,"fixed wire size");
    for (std::size_t size:{std::size_t(0),std::size_t(915),std::size_t(917)})
        check(!mpvr::decode(bytes.data(),size,frame),"incorrect length rejected before read");
    for (auto offset:{0u,8u,16u}) {
        auto bad=bytes;bad[offset]=127;
        check(!mpvr::decode(bad.data(),bad.size(),frame),"bad magic/side/flags");
    }
    for (float bad:{std::numeric_limits<float>::quiet_NaN(),std::numeric_limits<float>::infinity(),11.f}) {
        auto invalid=bytes;put_float(invalid.data()+20,bad);
        check(!mpvr::decode(invalid.data(),invalid.size(),frame),"invalid pose rejected");
    }
    for (auto offset:{32u,60u,88u}) {
        auto bad=bytes;put_float(bad.data()+offset,0.f);
        check(!mpvr::decode(bad.data(),bad.size(),frame),"zero quaternion rejected");
    }
    auto bad=bytes;put_float(bad.data()+48,.01f);
    check(!mpvr::decode(bad.data(),bad.size(),frame),"root must be identity");
    bad=bytes;put_float(bad.data()+76,2.f);
    check(!mpvr::decode(bad.data(),bad.size(),frame),"bone coordinates bounded");
    auto missing=packet(0,2,false);
    check(mpvr::decode(missing.data(),missing.size(),frame) && !frame.valid,"explicit loss supported");
    mpvr::State state;frame.valid=true;frame.sequence=1;
    check(state.accept(frame,0) && state.live(.499),"valid sample active");
    check(!state.live(.5),"timeout exactly 500ms");
    check(!state.accept(frame,.1),"duplicate ignored");
    frame.sequence=0;check(!state.accept(frame,.2),"out of order ignored");
    check(state.accept(frame,.6),"sender restart after timeout");
    frame.sequence=1;frame.valid=false;
    check(state.accept(frame,.61) && !state.live(.61),"explicit loss immediate");
    frame.valid=true;frame.sequence=0xffffffffu;
    mpvr::State wrap;check(wrap.accept(frame,1),"last sequence accepted");
    frame.sequence=0;check(wrap.accept(frame,1.01),"uint32 wrap accepted");
    check(!state.accept(frame,std::numeric_limits<double>::quiet_NaN()),"invalid time");
    mpvr::Control control;
    check(control.pulse(1,300) && control.pressed(1.1,true),"explicit pulse");
    check(!control.pressed(1.1,false) && !control.pressed(1.301,true),"loss/deadline releases trigger");
    check(!control.pulse(2,501),"unbounded hold rejected");
    check(control.pulse(2,0) && !control.pressed(2,true),"manual release");
    std::cout<<"Protocol, validation, ordering, timeout and release passed\n";
}
