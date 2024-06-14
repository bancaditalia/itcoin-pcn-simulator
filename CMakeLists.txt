CMAKE_MINIMUM_REQUIRED(VERSION 3.12)
PROJECT(CLOTH-ROSS VERSION 1.0
                   DESCRIPTION "CLoTH over ROSS"
                   LANGUAGES C CXX)

SET(MODEL_NAME "itcoin-pcn-simulator")

# Set default build type to Release
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Debug)
    message(STATUS "Build type not specified: Use Debug by default. If you want to perform a Release build call with -DCMAKE_BUILD_TYPE=Release")
endif(NOT CMAKE_BUILD_TYPE)

# configure local 'usr' directory for dependencies (e.g. ROSS)
set(USR_DIR ${CMAKE_BINARY_DIR}/usr CACHE PATH "Installation directory for dependencies")
file(MAKE_DIRECTORY ${USR_DIR})
file(CREATE_LINK "${USR_DIR}/lib" "${USR_DIR}/lib64" SYMBOLIC)

include(ExternalProject)

# find dependencies
#
# On Fedora (tested with 38), you will need additional passes (source:
# https://brandonrozek.com/blog/openmpi-fedora/):
#
# Not only:
#     dnf install openmpi-devel
#
# But also:
#     source /etc/profile.d/modules.sh
#     module load mpi/openmpi-x86_64
find_package(MPI REQUIRED)

# Add ROSS as External Project
set(ROSS_LIBRARIES ${USR_DIR}/lib/libROSS.a)

ExternalProject_Add(ross
    GIT_REPOSITORY https://github.com/ROSS-org/ROSS
    GIT_TAG v8.0.0
    GIT_PROGRESS true
    CMAKE_ARGS
        -DCMAKE_C_COMPILER=${CMAKE_C_COMPILER}
        -DCMAKE_CXX_COMPILER=${CMAKE_CXX_COMPILER}
        -DCMAKE_INSTALL_PREFIX=${USR_DIR}
        -DCMAKE_BUILD_TYPE=${CMAKE_BUILD_TYPE}
    BUILD_BYPRODUCTS ${ROSS_LIBRARIES}
)

# Add Metis as External Project

ExternalProject_Add(gklib
  	GIT_REPOSITORY https://github.com/KarypisLab/GKlib.git
  	GIT_TAG 8bd6bad750b2b0d90800c632cf18e8ee93ad72d7
  	GIT_PROGRESS true
		CMAKE_ARGS
			-DCMAKE_INSTALL_PREFIX=${USR_DIR}
		BUILD_BYPRODUCTS ${USR_DIR}/lib/libGKlib.a
)

ExternalProject_Add(metis
  	GIT_REPOSITORY https://github.com/KarypisLab/METIS
  	GIT_TAG v5.2.1
  	GIT_PROGRESS true
  	PATCH_COMMAND git apply "${CMAKE_CURRENT_LIST_DIR}/utilities/metis.diff" || git apply --reverse --check "${CMAKE_CURRENT_LIST_DIR}/utilities/metis.diff"
		CONFIGURE_COMMAND cd ../metis && make config shared=1 i64=1 r64=1 prefix=${USR_DIR}
		BUILD_COMMAND cd ../metis/build && make
		INSTALL_COMMAND cd ../metis/build && make install
		UPDATE_COMMAND ""
		BUILD_BYPRODUCTS ${USR_DIR}/lib/libmetis.so
)

add_dependencies(metis gklib)

# Create the main executable

add_executable(${MODEL_NAME}
	src/utils/utils.c
	src/utils/logging.c
	src/utils/hash_table.c
	src/utils/array.c
	src/utils/heap.c
	src/utils/list.c
	src/main.c
	src/model/load.c
	src/model/blockchain.c
	src/model/mapping.c
	src/model/message.c
	src/model/pcn_node.c
	src/model/global.c
	src/model/event_trace.c
	src/features/payments.c
	src/features/routing.c
	src/features/htlc.c
	src/features/submarine_swaps.c
	src/features/network.c
)

add_dependencies(${MODEL_NAME} ross)

target_include_directories(${MODEL_NAME}
	PUBLIC
	${MPI_C_INCLUDE_DIRS}
	${USR_DIR}/include
)

target_link_libraries(${MODEL_NAME}
	${ROSS_LIBRARIES}
	m
	${MPI_C_LIBRARIES}
)

target_link_directories(${MODEL_NAME}
	PRIVATE
	${USR_DIR}/lib
)
