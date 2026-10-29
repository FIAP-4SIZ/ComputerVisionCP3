#include "test_helpers.h"
#include <iostream>
#include <iterator>
#include <vector>
int main() {
    const std::vector<unsigned char> bytes((std::istreambuf_iterator<char>(std::cin)),{});
    mpvr::Frame frame;
    if (!mpvr::decode(bytes.data(),bytes.size(),frame)) return 2;
    std::cout<<frame.side<<" "<<frame.sequence<<" "<<frame.valid<<" "<<frame.pose.position[0]<<"\n";
}
