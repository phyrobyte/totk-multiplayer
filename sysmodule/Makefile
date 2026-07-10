# TOTK Multiplayer sysmodule — build skeleton (devkitPro / libnx)
#
# This is a STUB Makefile documenting the intended build. It is not runnable until
# devkitPro + libnx are installed (Phase 1, once the console is modded). Fill in the
# devkitPro-provided switch_rules include and it becomes a standard libnx sysmodule.
#
#   1. Install devkitPro + switch-dev + libnx  (https://devkitpro.org/wiki/Getting_Started)
#   2. Uncomment the include lines below.
#   3. make            -> builds an .nsp sysmodule
#   4. Copy to  sdcard:/atmosphere/contents/<program-id>/  and reboot.

# ifeq ($(strip $(DEVKITPRO)),)
# $(error "Set up devkitPro and export DEVKITPRO before building")
# endif
# include $(DEVKITPRO)/libnx/switch_rules

TARGET   := totk-mp-sysmodule
SOURCES  := source
BUILD    := build
INCLUDES := include

# libnx sysmodules run with a small heap; tune in the .json config alongside.
# See https://github.com/switchbrew/switch-examples for reference sysmodule setup.

.PHONY: all clean
all:
	@echo "Skeleton only. Install devkitPro/libnx, then wire up switch_rules to build."

clean:
	@rm -rf $(BUILD)
