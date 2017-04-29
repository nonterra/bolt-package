###############################################################################
#
# Converts a machine name (armv6, x86_64) or a target triplet
# (armv6-linux-gnueabihf, x86_64-pc-linux-gnu) to the corresponding kernel
# ARCH.
#
# $1: a machine name or target triplet
#
# Prints the corresponding kernel ARCH name.
#
###############################################################################
bh_kernel_arch_for_target()
{
    local uname="`echo $1 | cut -d'-' -f1`"

    echo $(
        # The following is stolen from a kernel makefile
        echo "$uname" | sed -e 's/i.86/x86/'      -e 's/x86_64/x86/'     \
                          -e 's/sun4u/sparc64/'                          \
                          -e 's/arm.*/arm/'     -e 's/sa110/arm/'        \
                          -e 's/s390x/s390/'    -e 's/parisc64/parisc/'  \
                          -e 's/ppc.*/powerpc/' -e 's/mips.*/mips/'      \
                          -e 's/sh[234].*/sh/'  -e 's/aarch64.*/arm64/'
    )
}

###############################################################################
#
# Converts a machine name (armv6, x86_64) or a target triplet
# (armv6-linux-gnueabihf, x86_64-pc-linux-gnu) to the corresponding musl
# architecture.
#
# $1: a machine name or target triplet
#
# Prints the corresponding musl architecture name.
#
###############################################################################
bh_musl_arch_for_target()
{
    case "$1" in
        arm*)
            echo "arm"
            ;;
        aarch64*)
            echo "aarch64"
            ;;
        i?86-nt32*)
            echo "nt32"
            ;;
        i?86*)
            echo "i386"
            ;;
        x86_64-x32*|x32*|x86_64*x32)
            echo "x32"
            ;;
        x86_64-nt64*)
            echo "nt64"
            ;;
        x86_64*)
            echo "x86_64"
            ;;
        mips64*|mipsisa64*)
            echo "mips64"
            ;;
        mips*)
            echo "mips"
            ;;
        microblaze*)
            echo "microblaze"
            ;;
        or1k*)
            echo "or1k"
            ;;
        powerpc64*|ppc64*)
            echo "powerpc64"
            ;;
        powerpc*)
            echo "powerpc"
            ;;
        sh[1-9bel-]*|sh|superh*)
            echo "sh"
            ;;
        s390x*)
            echo "s390x"
            ;;
    esac
}

###############################################################################
#
# Takes a machine name as supported by the make.sh bootstrap script and spits
# out the default CPU optimizations with which to configure GCC.
#
# $1: a supported machine name
#
# Prints the corresponding CPU default settings.
#
###############################################################################
bh_gcc_config_for_machine()
{
    case "$1" in
        aarch64*)
            echo "--enable-fix-cortex-a53-843419"
            ;;
        armv4t*)
            echo "--with-arch=armv4t --with-float=soft"
            ;;
        armv6*)
            echo "--with-arch=armv6 --with-float=hard --with-fpu=vfp"
            ;;
        armv7a*)
            echo "--with-arch=armv7-a --with-float=hard --with-fpu=vfpv3-d16"
            ;;
        i?86*)
            echo "--with-tune=generic"
            ;;
        mips64el*)
            echo "--with-arch=mips64r2 --with-float=hard"
            ;;
        mips*el*)
            echo "--with-arch=mips32r2 --with-float=hard"
            ;;
        powerpc64el*|powerpc64le*|ppc64el*)
            echo "--enable-secureplt --with-abi=elfv2"
            ;;
        powerpc*)
            echo "--enable-secureplt --with-float=hard --with-cpu=default32 --with-long-double-64"
            ;;
        x86_64*)
            echo "--with-tune=generic"
            ;;
    esac
}

###############################################################################
#
# Takes a <machine>-<vendor>-<os> target triplet and inserts 'xxx' for the 
# vendor part. This is commonly used to trigger a cross compilation.
#
# $1: a target triplet
#
# Prints the modified target triplet.
#
###############################################################################
bh_spoof_target_triplet()
{
    echo "$1" | \
        sed 's/\([^-]\+\)-\([^-]\+-\)\?\([^-]\+\)-\([^-]\+\)/\1-xxx-\3-\4/g'
}
