# ============================================================================
# NovaX AI OS — Plymouth Boot Splash + LUKS Password Screen
# ============================================================================
# Cyberpunk matrix theme matching the NovaX desktop aesthetic.
# Green digital rain, ternary triangle logo, styled LUKS password prompt.
# ============================================================================
{ config, pkgs, lib, ... }:

{
  boot.plymouth = {
    enable = true;
    theme = "novax";
    themePackages = [
      (pkgs.stdenv.mkDerivation {
        pname = "plymouth-theme-novax";
        version = "2.0.0";

        src = pkgs.writeTextDir "placeholder" "";

        buildInputs = [ pkgs.imagemagick ];

        buildPhase = ''
          mkdir -p novax

          # ── Logo: Ternary triangle with glow effect ──
          ${pkgs.imagemagick}/bin/convert \
            -size 300x300 xc:transparent \
            -fill 'none' -stroke '#00ff4180' -strokewidth 5 \
            -draw "polygon 150,15 15,275 285,275" \
            -fill 'none' -stroke '#00ff41' -strokewidth 2 \
            -draw "polygon 150,30 35,260 265,260" \
            -fill '#00110a' \
            -draw "polygon 150,45 50,248 250,248" \
            -fill '#00ff41' \
            -font Helvetica-Bold -pointsize 42 \
            -gravity center -annotate +0+30 "NOVAX" \
            -fill '#00cc33' \
            -font Helvetica -pointsize 16 \
            -gravity center -annotate +0+65 "AI OPERATING SYSTEM" \
            novax/logo.png

          # ── Active dot (bright green) ──
          ${pkgs.imagemagick}/bin/convert \
            -size 12x12 xc:transparent \
            -fill '#00ff41' \
            -draw "circle 6,6 6,1" \
            novax/dot-active.png

          # ── Inactive dot (dim green) ──
          ${pkgs.imagemagick}/bin/convert \
            -size 12x12 xc:transparent \
            -fill '#003311' \
            -draw "circle 6,6 6,1" \
            novax/dot-dim.png

          # ── Password field background (dark rounded box) ──
          ${pkgs.imagemagick}/bin/convert \
            -size 400x50 xc:transparent \
            -fill '#0a1a0f' \
            -stroke '#00ff41' -strokewidth 1 \
            -draw "roundrectangle 0,0 399,49 8,8" \
            novax/passbox.png

          # ── Password bullet (filled green dot for each char typed) ──
          ${pkgs.imagemagick}/bin/convert \
            -size 14x14 xc:transparent \
            -fill '#00ff41' \
            -draw "circle 7,7 7,2" \
            novax/passbullet.png

          # ── Lock icon ──
          ${pkgs.imagemagick}/bin/convert \
            -size 40x50 xc:transparent \
            -fill 'none' -stroke '#00ff41' -strokewidth 2 \
            -draw "roundrectangle 5,22 35,48 4,4" \
            -fill 'none' -stroke '#00ff41' -strokewidth 2 \
            -draw "arc 10,2 30,30 0,180" \
            novax/lock.png

          # ── Matrix rain column (vertical strip of fading characters) ──
          ${pkgs.imagemagick}/bin/convert \
            -size 20x600 xc:transparent \
            -fill '#00ff4108' -font Courier -pointsize 14 \
            -gravity north \
            -annotate +0+0   "1" \
            -annotate +0+20  "0" \
            -annotate +0+40  "-1" \
            -annotate +0+60  "0" \
            -annotate +0+80  "1" \
            -fill '#00ff4115' \
            -annotate +0+100 "-1" \
            -annotate +0+120 "1" \
            -annotate +0+140 "0" \
            -fill '#00ff4125' \
            -annotate +0+160 "1" \
            -annotate +0+180 "-1" \
            -annotate +0+200 "0" \
            -fill '#00ff4140' \
            -annotate +0+220 "1" \
            -annotate +0+240 "0" \
            -annotate +0+260 "-1" \
            -fill '#00ff4160' \
            -annotate +0+280 "0" \
            -annotate +0+300 "1" \
            -annotate +0+320 "-1" \
            -fill '#00ff4190' \
            -annotate +0+340 "1" \
            -annotate +0+360 "0" \
            -annotate +0+380 "-1" \
            -fill '#00ff41' \
            -annotate +0+400 "1" \
            -annotate +0+420 "0" \
            novax/rain.png

          # ── Plymouth manifest ──
          cat > novax/novax.plymouth <<'PLYMOUTH'
[Plymouth Theme]
Name=NovaX AI OS
Description=Cyberpunk matrix boot splash for NovaX AI Operating System
ModuleName=script

[script]
ImageDir=/usr/share/plymouth/themes/novax
ScriptFile=/usr/share/plymouth/themes/novax/novax.script
PLYMOUTH

          # ── Plymouth animation script ──
          cat > novax/novax.script <<'SCRIPT'
# ============================================================
# NovaX Plymouth Theme — Cyberpunk Matrix
# ============================================================
# Deep black background with green digital rain,
# ternary triangle logo, styled LUKS password prompt.
# ============================================================

# ── Background: near-black with subtle green tint ──
Window.SetBackgroundTopColor(0.0, 0.04, 0.02);
Window.SetBackgroundBottomColor(0.0, 0.0, 0.0);

screenW = Window.GetWidth();
screenH = Window.GetHeight();
centerX = screenW / 2;
centerY = screenH / 2;

# ── Matrix rain columns ──
rain_img = Image("rain.png");
num_columns = 30;
for (i = 0; i < num_columns; i++) {
    rain[i].sprite = Sprite(rain_img);
    rain[i].x = i * (screenW / num_columns) + Math.Int(Math.Random() * 20);
    rain[i].y = Math.Int(Math.Random() * screenH) - 600;
    rain[i].speed = 1 + Math.Int(Math.Random() * 3);
    rain[i].sprite.SetPosition(rain[i].x, rain[i].y, 0);
    rain[i].sprite.SetOpacity(0.15 + Math.Random() * 0.25);
}

# ── Logo (centered, upper third) ──
logo_img = Image("logo.png");
logo_sprite = Sprite(logo_img);
logo_sprite.SetPosition(centerX - logo_img.GetWidth() / 2,
                         centerY - logo_img.GetHeight() / 2 - 80, 5);

# ── Status text ──
status_text = Image.Text("Initializing ternary subsystems...",
                          0.0, 1.0, 0.25,    # green
                          "Monospace 12");
status_sprite = Sprite(status_text);
status_sprite.SetPosition(centerX - status_text.GetWidth() / 2,
                           centerY + 100, 5);

# ── Progress dots (3 — ternary) ──
dot_active = Image("dot-active.png");
dot_dim = Image("dot-dim.png");
for (i = 0; i < 3; i++) {
    dots[i].sprite = Sprite(dot_dim);
    dots[i].sprite.SetPosition(centerX - 24 + i * 24, centerY + 130, 5);
}

# ── Animation ──
counter = 0;

fun refresh_callback() {
    counter++;

    # Animate matrix rain
    for (i = 0; i < num_columns; i++) {
        rain[i].y = rain[i].y + rain[i].speed;
        if (rain[i].y > screenH) {
            rain[i].y = -600;
            rain[i].x = i * (screenW / num_columns) + Math.Int(Math.Random() * 20);
        }
        rain[i].sprite.SetPosition(rain[i].x, rain[i].y, 0);
    }

    # Pulse the active dot
    active = Math.Int(counter / 20) % 3;
    for (i = 0; i < 3; i++) {
        if (i == active)
            dots[i].sprite.SetImage(dot_active);
        else
            dots[i].sprite.SetImage(dot_dim);
    }

    # Subtle logo pulse (opacity between 0.85 and 1.0)
    pulse = 0.925 + Math.Sin(counter / 10.0) * 0.075;
    logo_sprite.SetOpacity(pulse);
}

Plymouth.SetRefreshFunction(refresh_callback);

# ── Boot progress text updates ──
boot_messages = 0;
fun message_callback(text) {
    boot_messages++;
    # Update status text with actual boot stage
    if (text != "") {
        new_text = Image.Text(text, 0.0, 1.0, 0.25, "Monospace 11");
        status_sprite.SetImage(new_text);
        status_sprite.SetPosition(centerX - new_text.GetWidth() / 2,
                                   centerY + 100, 5);
    }
}

Plymouth.SetMessageFunction(message_callback);

# ── LUKS Password Prompt ──────────────────────────────────────
# This is the cyberpunk login screen.
# Shows lock icon, password box with green border, bullet dots.

passbox_img = Image("passbox.png");
lock_img = Image("lock.png");
bullet_img = Image("passbullet.png");

passbox_sprite = Sprite();
lock_sprite = Sprite();
prompt_sprite = Sprite();
bullet_sprites = [];

password_visible = 0;

fun display_password_callback(prompt_text, num_bullets) {
    password_visible = 1;

    # Hide the progress dots and status during password
    for (i = 0; i < 3; i++)
        dots[i].sprite.SetOpacity(0);
    status_sprite.SetOpacity(0);

    # Lock icon
    lock_sprite.SetImage(lock_img);
    lock_sprite.SetPosition(centerX - 20, centerY + 55, 10);

    # Prompt text: "Enter passphrase to unlock NovaX"
    prompt_img = Image.Text("Enter passphrase to unlock NovaX",
                             0.0, 1.0, 0.25, "Monospace 13");
    prompt_sprite.SetImage(prompt_img);
    prompt_sprite.SetPosition(centerX - prompt_img.GetWidth() / 2,
                               centerY + 110, 10);

    # Password box
    passbox_sprite.SetImage(passbox_img);
    passbox_sprite.SetPosition(centerX - 200, centerY + 140, 10);

    # Clear old bullets
    for (i = 0; i < 40; i++) {
        if (bullet_sprites[i])
            bullet_sprites[i].SetOpacity(0);
    }

    # Draw bullet dots for each character typed
    for (i = 0; i < num_bullets && i < 30; i++) {
        bullet_sprites[i] = Sprite(bullet_img);
        bullet_sprites[i].SetPosition(
            centerX - 185 + i * 18,
            centerY + 158,
            11
        );
        bullet_sprites[i].SetOpacity(1.0);
    }
}

Plymouth.SetDisplayPasswordFunction(display_password_callback);

# ── Normal boot complete ──
fun quit_callback() {
    # Fade everything out
    logo_sprite.SetOpacity(0);
    status_sprite.SetOpacity(0);
    for (i = 0; i < 3; i++)
        dots[i].sprite.SetOpacity(0);
    for (i = 0; i < num_columns; i++)
        rain[i].sprite.SetOpacity(0);
    if (password_visible) {
        passbox_sprite.SetOpacity(0);
        lock_sprite.SetOpacity(0);
        prompt_sprite.SetOpacity(0);
        for (i = 0; i < 40; i++) {
            if (bullet_sprites[i])
                bullet_sprites[i].SetOpacity(0);
        }
    }
}

Plymouth.SetQuitFunction(quit_callback);

SCRIPT
        '';

        installPhase = ''
          mkdir -p $out/share/plymouth/themes/novax
          cp novax/* $out/share/plymouth/themes/novax/
        '';

        meta = {
          description = "NovaX AI OS Plymouth boot splash — cyberpunk matrix theme";
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
