# ============================================================================
# NovaX AI OS — Nix Package Overlay
# ============================================================================
# Custom package definitions for NovaX components that are not in nixpkgs.
# ============================================================================
final: prev:
{
  # ── NovaLang VM — Rust-based ternary language runtime ───────────────────
  # Built from source at /opt/novax/novalang-vm/
  # Produces: novalang, nova-lsp, nova-fmt binaries
  novalang-vm = final.rustPlatform.buildRustPackage rec {
    pname = "novalang";
    version = "1.4.0";

    # Source: the novalang-vm directory from the NovaX repo
    # During ISO build, this should be copied/included via the flake
    src = ../novalang-vm;

    cargoLock = {
      lockFile = ../novalang-vm/Cargo.lock;
    };

    nativeBuildInputs = with final; [
      pkg-config
    ];

    buildInputs = with final; [
      openssl
    ];

    # Release profile with LTO for maximum performance
    buildType = "release";

    # Install all three binaries
    postInstall = ''
      # novalang, nova-lsp, nova-fmt are all built by cargo
      # They should be in $out/bin/ automatically
      echo "NovaLang VM v${version} installed:"
      ls -la $out/bin/
    '';

    meta = with final.lib; {
      description = "NovaLang — Ternary-first language VM for NovaX AI OS";
      homepage = "https://github.com/novax-ai/novalang";
      license = licenses.mit;
      platforms = platforms.linux;
      mainProgram = "novalang";
    };
  };

  # ── Trit Engine — Ternary arithmetic accelerator ────────────────────────
  # If a separate Rust crate exists for the trit engine, define it here.
  # Currently the trit engine is built into novalang-vm (talu.rs, tmatmul.rs)
  # so this is a placeholder for future extraction.
  # trit-engine = final.rustPlatform.buildRustPackage rec {
  #   pname = "trit-engine";
  #   version = "0.1.0";
  #   src = ../trit-engine;
  #   cargoLock.lockFile = ../trit-engine/Cargo.lock;
  #   meta.description = "Ternary arithmetic accelerator for NovaX";
  # };

  # ── Edge-TTS — Python package for voice synthesis ───────────────────────
  # Ensure edge-tts is available if not already in nixpkgs
  python312 = prev.python312.override {
    packageOverrides = pfinal: pprev: {
      edge-tts = pprev.edge-tts or (pfinal.buildPythonPackage rec {
        pname = "edge-tts";
        version = "6.1.12";
        format = "setuptools";

        src = pfinal.fetchPypi {
          inherit pname version;
          hash = "sha256-PLACEHOLDER";  # Replace with actual hash on first build
        };

        propagatedBuildInputs = with pfinal; [
          aiohttp
          certifi
        ];

        doCheck = false;

        meta = {
          description = "Use Microsoft Edge's online TTS service from Python";
          homepage = "https://github.com/rany2/edge-tts";
        };
      });
    };
  };

  # ── NovaX File Bundle — installs all .nova, .py, .js, web/ to /opt/novax ─
  # This package copies the entire NovaX runtime to /opt/novax
  novax-files = final.stdenv.mkDerivation {
    pname = "novax-files";
    version = "6.0.0";

    # The source is the entire NovaX directory
    src = final.lib.cleanSourceWith {
      src = ../.;
      filter = path: type:
        let
          baseName = builtins.baseNameOf path;
          # Exclude build artifacts, Windows binaries, git, etc.
          excluded = [
            ".git" "__pycache__" "ai_env" "archive" "dumps"
            "novalang-vm"  # Built separately
            "nixos"        # This config directory
            ".session_token" ".vault_key"
          ];
          isExcluded = builtins.any (e: baseName == e) excluded;
          # Exclude Windows-only files
          isWindowsBinary = final.lib.hasSuffix ".exe" baseName
                        || final.lib.hasSuffix ".bat" baseName
                        || final.lib.hasSuffix ".ps1" baseName
                        || final.lib.hasSuffix ".vbs" baseName;
        in
        !isExcluded && !isWindowsBinary;
    };

    installPhase = ''
      mkdir -p $out/share/novax
      cp -r . $out/share/novax/

      # Create activation script that syncs to /opt/novax
      mkdir -p $out/bin
      cat > $out/bin/novax-install <<'SCRIPT'
      #!/bin/sh
      echo "Installing NovaX files to /opt/novax..."
      rsync -a --delete \
        --exclude '.paths-patched' \
        --exclude 'logs/*' \
        --exclude 'tmp/*' \
        --exclude 'data/*' \
        --exclude 'models/*' \
        --exclude 'snapshots/*' \
        "$1/share/novax/" /opt/novax/
      chown -R nova:users /opt/novax
      echo "NovaX files installed."
      SCRIPT
      chmod +x $out/bin/novax-install
    '';

    meta = {
      description = "NovaX AI OS runtime files";
    };
  };
}
