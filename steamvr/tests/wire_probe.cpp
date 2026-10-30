#include "test_helpers.h"
#include <iostream>
#include <iterator>
#include <vector>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif
int main() {
#ifdef _WIN32
    // stdin em modo texto interpreta 0x1A como EOF e transforma CRLF. Pacotes
    // float32 precisam chegar byte a byte, assim como no socket do driver.
    if (_setmode(_fileno(stdin),_O_BINARY)==-1) return 3;
#endif
    const std::vector<unsigned char> bytes((std::istreambuf_iterator<char>(std::cin)),{});
    mpvr::Frame frame;
    if (!mpvr::decode(bytes.data(),bytes.size(),frame)) {
        std::cerr<<"Invalid packet: received "<<bytes.size()<<" bytes; expected "<<mpvr::packet_size<<"\n";
        return 2;
    }
    std::cout<<frame.side<<" "<<frame.sequence<<" "<<frame.valid<<" "<<frame.pose.position[0]<<"\n";
}
