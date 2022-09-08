FROM ubuntu:20.04

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive \
    apt-get install -y \
    ssh \
    wget \
    software-properties-common \
    git && \
    rm -rf /var/lib/apt/lists/*

RUN wget -O /etc/apt/trusted.gpg.d/openfoam.asc https://dl.openfoam.org/gpg.key
RUN add-apt-repository http://dl.openfoam.org/ubuntu

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive \
    apt-get install -y openfoam10 openmpi-bin && \
    rm -rf /var/lib/apt/lists/*

ENV PATH="/opt/ThirdParty-10/platforms/linux64Gcc/gperftools-svn/bin:/opt/paraviewopenfoam56/bin:/opt/ThirdParty-10/platforms/linux64Gcc/cmake-*/bin:/opt/site/10/platforms/linux64GccDPInt32Opt/bin:/opt/openfoam10/platforms/linux64GccDPInt32Opt/bin:/opt/openfoam10/bin:/opt/openfoam10/wmake:$PATH" \
    LD_LIBRARY_PATH="/opt/ThirdParty-10/platforms/linux64Gcc/gperftools-svn/lib:/opt/openfoam10/platforms/linux64GccDPInt32Opt/lib/paraview-5.6:/opt/paraviewopenfoam56/lib:/opt/openfoam10/platforms/linux64GccDPInt32Opt/lib/openmpi-system:/opt/ThirdParty-10/platforms/linux64GccDPInt32/lib/openmpi-system:/usr/lib/x86_64-linux-gnu/openmpi/lib:/opt/site/10/platforms/linux64GccDPInt32Opt/lib:/opt/openfoam10/platforms/linux64GccDPInt32Opt/lib:/opt/ThirdParty-10/platforms/linux64GccDPInt32/lib:/opt/openfoam10/platforms/linux64GccDPInt32Opt/lib/dummy" \
    FOAM_APP="/opt/openfoam10/applications" \
    FOAM_APPBIN="/opt/openfoam10/platforms/linux64GccDPInt32Opt/bin" \
    FOAM_ETC="/opt/openfoam10/etc" \
    FOAM_EXT_LIBBIN="/opt/ThirdParty-10/platforms/linux64GccDPInt32/lib" \
    FOAM_INST_DIR="/opt" \
    FOAM_JOB_DIR="/opt/jobControl" \
    FOAM_LIBBIN="/opt/openfoam10/platforms/linux64GccDPInt32Opt/lib" \
    FOAM_MPI="openmpi-system" \
    FOAM_SITE_APPBIN="/opt/site/10/platforms/linux64GccDPInt32Opt/bin" \
    FOAM_SITE_LIBBIN="/opt/site/10/platforms/linux64GccDPInt32Opt/lib" \
    FOAM_SOLVERS="/opt/openfoam10/applications/solvers" \
    FOAM_SRC="/opt/openfoam10/src" \
    FOAM_TUTORIALS="/opt/openfoam10/tutorials" \
    FOAM_UTILITIES="/opt/openfoam10/applications/utilities" \
    MPI_ARCH_PATH="/usr/lib/x86_64-linux-gnu/openmpi" \
    MPI_BUFFER_SIZE="20000000" \
    PV_PLUGIN_PATH="/opt/openfoam10/platforms/linux64GccDPInt32Opt/lib/paraview-5.6" \
    ParaView_DIR="/opt/paraviewopenfoam56" \
    ParaView_GL="mesa" \
    ParaView_INCLUDE_DIR="/opt/paraviewopenfoam56/include/paraview-5.6" \
    ParaView_LIB_DIR="/opt/paraviewopenfoam56/lib" \
    ParaView_MAJOR="5.6" \
    ParaView_VERSION="5.6.0" \
    WM_ARCH="linux64" \
    WM_ARCH_OPTION="64" \
    WM_CC="gcc" \
    WM_CFLAGS="-m64 -fPIC" \
    WM_COMPILER="Gcc" \
    WM_COMPILER_LIB_ARCH="64" \
    WM_COMPILER_TYPE="system" \
    WM_COMPILE_OPTION="Opt" \
    WM_CXX="g++" \
    WM_CXXFLAGS="-m64 -fPIC -std=c++0x" \
    WM_DIR="/opt/openfoam10/wmake" \
    WM_LABEL_OPTION="Int32" \
    WM_LABEL_SIZE="32" \
    WM_LDFLAGS="-m64" \
    WM_LINK_LANGUAGE="c++" \
    WM_MPLIB="SYSTEMOPENMPI" \
    WM_OPTIONS="linux64GccDPInt32Opt" \
    WM_OSTYPE="POSIX" \
    WM_PRECISION_OPTION="DP" \
    WM_PROJECT="OpenFOAM" \
    WM_PROJECT_DIR="/opt/openfoam10" \
    WM_PROJECT_INST_DIR="/opt" \
    WM_PROJECT_VERSION="10" \
    WM_THIRD_PARTY_DIR="/opt/ThirdParty-10"