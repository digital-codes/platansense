#idf_component_register(
#    SRCS "modadpcm.c"
#    INCLUDE_DIRS "."
    #PRIV_REQUIRES esp_audio_codec
#)


# SPDX-License-Identifier: MIT

# Create an INTERFACE library for our C module.
#add_library(module_adpcm INTERFACE  idf::esp_audio_codec)
add_library(module_adpcm INTERFACE )

# Add our source files to the lib
target_sources(module_adpcm INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/modadpcm.c
)



target_include_directories(module_adpcm INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}
    #${CMAKE_SOURCE_DIR}/../esp-adf/components/esp-adf-libs/esp_audio_codec/include
)

#target_link_libraries(module_adpcm INTERFACE idf::esp_audio_codec)
target_link_libraries(module_adpcm INTERFACE)
target_link_libraries(usermod INTERFACE module_adpcm)

