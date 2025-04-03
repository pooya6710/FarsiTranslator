
{pkgs}: {
  deps = [
    pkgs.tk
    pkgs.tcl
    pkgs.qhull
    pkgs.pkg-config
    pkgs.gtk3
    pkgs.gobject-introspection
    pkgs.ghostscript
    pkgs.freetype
    pkgs.cairo
    pkgs.imagemagickBig
    pkgs.ffmpeg-full
    pkgs.ffmpeg
    pkgs.postgresql
    pkgs.openssl
  ];
}
