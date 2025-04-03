#!/bin/bash

# جایگزینی مسیر ffmpeg در method_ffmpeg_advanced
sed -i "s|'/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg'|FFMPEG_PATH|g" telegram_fixes.py

# جایگزینی مسیر ffmpeg در method_ffmpeg_simple
sed -i "s|'/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg'|FFMPEG_PATH|g" telegram_fixes.py

# جایگزینی مسیر ffmpeg در method_ffmpeg_native
sed -i "s|'/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg'|FFMPEG_PATH|g" telegram_fixes.py

# جایگزینی مسیر ffmpeg در method_fallback
sed -i "s|'/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg'|FFMPEG_PATH|g" telegram_fixes.py

# جایگزینی مسیر ffmpeg در fallback_convert_video
sed -i "s|'/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg'|FFMPEG_PATH|g" telegram_fixes.py

echo "مسیرهای ffmpeg با موفقیت اصلاح شدند."