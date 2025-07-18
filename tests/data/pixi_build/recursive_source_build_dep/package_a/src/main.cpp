#include <iostream>
#include <package_b.h>

int main() {
    std::cout << "Package A application starting..." << std::endl;

    // Use the add function from package_b
    int result = package_b::add(5, 3);
    std::cout << "5 + 3 = " << result << std::endl;

    std::cout << "Package A application finished!" << std::endl;

    return 0;
}
