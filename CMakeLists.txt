cmake_minimum_required(VERSION 3.20)
project(RCRness C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

set(NESRECOMP_ROOT "${CMAKE_SOURCE_DIR}/nesrecomp")
include("${NESRECOMP_ROOT}/runner/runner.cmake")

list(APPEND CMAKE_PREFIX_PATH "${NESRECOMP_ROOT}/runner/external/SDL2/cmake")
find_package(SDL2 REQUIRED CONFIG)

add_executable(RCRness
    ${NESRECOMP_RUNNER_SOURCES}
    extras.c
    rcr_widescreen.c
    generated/rcr_full.c
    generated/rcr_dispatch.c
)

target_include_directories(RCRness PRIVATE
    ${NESRECOMP_RUNNER_INCLUDE_DIRS}
    ${CMAKE_SOURCE_DIR}
    ${SDL2_INCLUDE_DIRS}
)
target_link_libraries(RCRness PRIVATE ${SDL2_LIBRARIES})

if(WIN32)
    target_link_libraries(RCRness PRIVATE ws2_32)
    add_custom_command(TARGET RCRness POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${NESRECOMP_ROOT}/runner/external/SDL2/lib/x64/SDL2.dll"
            "$<TARGET_FILE_DIR:RCRness>"
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${CMAKE_SOURCE_DIR}/keybinds.ini"
            "$<TARGET_FILE_DIR:RCRness>")
endif()

if(MSVC)
    target_compile_options(RCRness PRIVATE /W3 /WX- /wd4102)
else()
    target_compile_options(RCRness PRIVATE -Wall -Wextra -Wno-unused-label)
endif()

target_compile_definitions(RCRness PRIVATE
    NESRECOMP_GAME_PLAYERS=2
    NESRECOMP_GAME_OAM_DMA_FILTER=1
    NESRECOMP_DEFAULT_REDUCE_SPRITE_FLICKER=1
    NESRECOMP_DEFAULT_CRT_FILTER=1
)
