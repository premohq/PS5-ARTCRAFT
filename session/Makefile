# artcraft-session.exe, an x86-64 Windows program, built with MinGW-w64 (Debian/Ubuntu: gcc-mingw-w64-x86-64) or
# with clang: make MINGW_CC="clang --target=x86_64-w64-windows-gnu".
MINGW_CC ?= x86_64-w64-mingw32-gcc
CFLAGS ?= -O2 -s -Wall -Wextra -Werror
LIBS = -lshlwapi -lshell32 -lole32 -luuid -lwintrust

artcraft-session.exe: artcraft-session.c
	$(MINGW_CC) $(CFLAGS) -municode -mwindows -o $@ $< $(LIBS)

clean:
	rm -f artcraft-session.exe

.PHONY: clean
