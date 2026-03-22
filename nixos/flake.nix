# ============================================================================
# NovaX AI OS — NixOS Flake
# ============================================================================
# Build ISO:  nix build .#nixosConfigurations.novax.config.system.build.isoImage
# Build VM:   nix build .#nixosConfigurations.novax.config.system.build.vm
# Rebuild:    sudo nixos-rebuild switch --flake .
# ============================================================================
{
  description = "NovaX AI Operating System — Ternary-Native AI OS";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    rust-overlay = {
      url = "github:oxalica/rust-overlay";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    # Lanzaboote — Secure Boot for NixOS
    lanzaboote = {
      url = "github:nix-community/lanzaboote/v0.4.2";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, rust-overlay, lanzaboote, ... }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs {
        inherit system;
        config = {
          allowUnfree = true;          # NVIDIA proprietary drivers
          cudaSupport = true;
        };
        overlays = [
          rust-overlay.overlays.default
          (import ./novax-overlay.nix)
        ];
      };
    in
    {
      nixosConfigurations.novax = nixpkgs.lib.nixosSystem {
        inherit system;
        specialArgs = { inherit pkgs; };
        modules = [
          lanzaboote.nixosModules.lanzaboote   # Secure Boot
          ./configuration.nix
          ./novax-services.nix
          ./boot-splash.nix
        ];
      };

      # Convenience: build a QEMU-testable VM
      # Usage: nix build .#vm && ./result/bin/run-novax-vm
      packages.${system}.vm =
        self.nixosConfigurations.novax.config.system.build.vm;

      # Convenience: build bootable ISO
      packages.${system}.iso =
        self.nixosConfigurations.novax.config.system.build.isoImage;
    };
}
