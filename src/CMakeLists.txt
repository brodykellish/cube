cmake_minimum_required(VERSION 3.12)

project(protodemo C CXX)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 20)

add_compile_options(-Wall -g3 -Og)
add_executable(protodemo
    protodemo.cpp
    piolib/piolib.c
    piolib/pio_rp1.c
)

add_custom_command(
    OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/protomatter.pio.h
    COMMAND python ${CMAKE_CURRENT_SOURCE_DIR}/assemble.py ${CMAKE_CURRENT_SOURCE_DIR}/protomatter.pio ${CMAKE_CURRENT_BINARY_DIR}/protomatter.pio.h
    DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/assemble.py ${CMAKE_CURRENT_SOURCE_DIR}/protomatter.pio
)

target_include_directories(protodemo PRIVATE include piolib/include)
