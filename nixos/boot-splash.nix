# ============================================================================
# NovaX AI OS — Plymouth Boot Splash
# ============================================================================
# Fast boot splash with NovaX branding. Shows ternary animation during boot.
# Designed to display for < 2 seconds on fast hardware.
# ============================================================================
{ config, pkgs, lib, ... }:

{
  # ── Plymouth Boot Splash ────────────────────────────────────────────────
  boot.plymouth = {
    enable = true;
    # Use the bgrt theme (shows manufacturer logo) or create custom
    theme = "novax";
    themePackages = [
      (pkgs.stdenv.mkDerivation {
        pname = "plymouth-theme-novax";
        version = "1.0.0";

        src = pkgs.writeTextDir "placeholder" "";

        buildInputs = [ pkgs.imagemagick ];

        buildPhase = ''
          mkdir -p novax

          # Generate NovaX logo as PNG (ternary triangle motif)
          # In production, replace with actual novax.ico converted asset
          ${pkgs.imagemagick}/bin/convert \
            -size 256x256 xc:transparent \
            -fill '#00ff88' \
            -stroke '#00ff88' \
            -strokewidth 3 \
            -draw "polygon 128,20 20,230 236,230" \
            -fill '#001a0d' \
            -draw "polygon 128,60 50,210 206,210" \
            -fill '#00ff88' \
            -font Helvetica -pointsize 28 \
            -gravity center -annotate +0+60 "NovaX" \
            -font Helvetica -pointsize 14 \
            -gravity center -annotate +0+90 "AI OS" \
            novax/logo.png

          # Create watermark/bullet for progress
          ${pkgs.imagemagick}/bin/convert \
            -size 16x16 xc:transparent \
            -fill '#00ff88' \
            -draw "circle 8,8 8,1" \
            novax/bullet.png

          # Plymouth theme script
          cat > novax/novax.plymouth <<'PLYMOUTH'
          [Plymouth Theme]
          Name=NovaX AI OS
          Description=NovaX Ternary AI Operating System boot splash
          ModuleName=script

          [script]
          ImageDir=/usr/share/plymouth/themes/novax
          ScriptFile=/usr/share/plymouth/themes/novax/novax.script
          PLYMOUTH

          # Plymouth script (animation)
          cat > novax/novax.script <<'SCRIPT'
          # NovaX Plymouth Boot Script — Ternary Animation
          # Background: deep black
          Window.SetBackgroundTopColor(0.0, 0.05, 0.02);
          Window.SetBackgroundBottomColor(0.0, 0.0, 0.0);

          # Load logo
          logo.image = Image("logo.png");
          logo.sprite = Sprite(logo.image);
          logo.sprite.SetX(Window.GetWidth() / 2 - logo.image.GetWidth() / 2);
          logo.sprite.SetY(Window.GetHeight() / 2 - logo.image.GetHeight() / 2 - 40);

          # Progress dots (ternary: 3 dots)
          bullet.image = Image("bullet.png");
          for (i = 0; i < 3; i++) {
            dots[i].sprite = Sprite(bullet.image);
            dots[i].sprite.SetX(Window.GetWidth() / 2 - 30 + i * 30);
            dots[i].sprite.SetY(Window.GetHeight() / 2 + 80);
            dots[i].sprite.SetOpacity(0.3);
          }

          # Animation counter
          counter = 0;

          fun refresh_callback() {
            counter++;
            active = Math.Int(counter / 15) % 3;
            for (i = 0; i < 3; i++) {
              if (i == active)
                dots[i].sprite.SetOpacity(1.0);
              else
                dots[i].sprite.SetOpacity(0.3);
            }
          }

          Plymouth.SetRefreshFunction(refresh_callback);

          # Password prompt (if encrypted disk)
          fun display_password_callback(prompt, bullets) {
            # Minimal password display
            pass_sprite = Sprite();
            pass_sprite.SetPosition(Window.GetWidth() / 2 - 100, Window.GetHeight() / 2 + 120, 1);
          }

          Plymouth.SetDisplayPasswordFunction(display_password_callback);

          # Hide messages (clean boot)
          fun message_callback(text) {
            # Suppress boot messages for clean look
          }

          Plymouth.SetMessageFunction(message_callback);
          SCRIPT
        '';

        installPhase = ''
          mkdir -p $out/share/plymouth/themes/novax
          cp novax/* $out/share/plymouth/themes/novax/
        '';

        meta = {
          description = "NovaX AI OS Plymouth boot splash theme";
        };
      })
    ];
  };

  # Ensure splash shows but doesn't delay boot
  boot.kernelParams = [
    "splash"
    "plymouth.enable=1"
  ];
}
