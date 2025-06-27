cmake_minimum_required(VERSION 3.16)
project(package-b VERSION 0.1.0)

# Create a shared library from a single source file
add_library(package-b SHARED src/package_b.cpp)

# Set library properties
set_target_properties(package-b PROPERTIES
    VERSION ${PROJECT_VERSION}
    SOVERSION 0
    CXX_STANDARD 11
    CXX_STANDARD_REQUIRED ON
)

# Install the library
install(TARGETS package-b
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
    RUNTIME DESTINATION bin
)

# Install headers if any
install(FILES src/package_b.h
    DESTINATION include
)
