# ============================================================================
# NovaX AI OS — Systemd Service Definitions
# ============================================================================
# 97 NovaLang microservices + 4 Python services + orchestrator
# All bound to 127.0.0.1, dependency-ordered, auto-restart on failure
#
# Boot order:
#   1. Redis + Meilisearch (defined in configuration.nix)
#   2. Ollama (defined in configuration.nix)
#   3. NovaX Static Server (port 8888) — serves dashboard immediately
#   4. NovaLang microservice fleet (86 services, staggered)
#   5. Python services (voice, digital twin, etc.)
#   6. Orchestrator (port 9999) — boots last, proxies everything
# ============================================================================
{ config, pkgs, lib, ... }:

let
  novaxRoot = "/opt/novax";
  novaxUser = "nova";
  novalangBin = "${pkgs.novalang-vm}/bin/novalang";

  # Python interpreter with NovaX deps
  novaxPython = pkgs.python312.withPackages (ps: with ps; [
    flask flask-socketio requests numpy torch transformers
    accelerate safetensors aiohttp websockets redis pyyaml
    psutil cryptography pynacl edge-tts httpx pillow scipy
  ]);

  # Common service config for all NovaLang services
  mkNovaService = { name, file, port, after ? [ "novax-infra-ready.target" ], wantedBy ? [ "novax-fleet.target" ] }: {
    description = "NovaX ${name} (port ${toString port})";
    inherit after wantedBy;
    environment = {
      NOVAX_ROOT = novaxRoot;
      PYTHONPATH = "${novaxRoot}:${novaxRoot}/core:${novaxRoot}/lib";
      NOVAX_HOST = "127.0.0.1";
      HOME = "/home/${novaxUser}";
      CUDA_VISIBLE_DEVICES = "0";
    };
    serviceConfig = {
      Type = "simple";
      ExecStart = "${novalangBin} ${novaxRoot}/${file}";
      WorkingDirectory = novaxRoot;
      User = novaxUser;
      Group = "users";
      Restart = "on-failure";
      RestartSec = 2;
      StartLimitBurst = 5;
      StartLimitIntervalSec = 60;
      # No TTY — equivalent to CREATE_NO_WINDOW
      StandardInput = "null";
      StandardOutput = "journal";
      StandardError = "journal";
      # Resource limits
      LimitNOFILE = 65536;
      # Logging identifier
      SyslogIdentifier = "novax-${name}";
    };
  };

  # Common service config for Python services
  mkPythonService = { name, file, port, after ? [ "novax-infra-ready.target" ], wantedBy ? [ "novax-fleet.target" ] }: {
    description = "NovaX ${name} (Python, port ${toString port})";
    inherit after wantedBy;
    environment = {
      NOVAX_ROOT = novaxRoot;
      PYTHONPATH = "${novaxRoot}:${novaxRoot}/core:${novaxRoot}/lib";
      NOVAX_HOST = "127.0.0.1";
      HOME = "/home/${novaxUser}";
      CUDA_VISIBLE_DEVICES = "0";
    };
    serviceConfig = {
      Type = "simple";
      ExecStart = "${novaxPython}/bin/python ${novaxRoot}/${file}";
      WorkingDirectory = novaxRoot;
      User = novaxUser;
      Group = "users";
      Restart = "on-failure";
      RestartSec = 2;
      StartLimitBurst = 5;
      StartLimitIntervalSec = 60;
      StandardInput = "null";
      StandardOutput = "journal";
      StandardError = "journal";
      LimitNOFILE = 65536;
      SyslogIdentifier = "novax-${name}";
    };
  };

in
{
  # ── Systemd Targets for Dependency Ordering ─────────────────────────────
  # Target: infrastructure ready (Redis + Meilisearch + Ollama are up)
  systemd.targets.novax-infra-ready = {
    description = "NovaX Infrastructure Ready";
    after = [
      "redis-novax.service"
      "meilisearch.service"
      "ollama.service"
      "network.target"
    ];
    requires = [
      "redis-novax.service"
      "meilisearch.service"
    ];
    wantedBy = [ "multi-user.target" ];
  };

  # Target: all fleet services started
  systemd.targets.novax-fleet = {
    description = "NovaX Microservice Fleet";
    after = [ "novax-infra-ready.target" ];
    wantedBy = [ "multi-user.target" ];
  };

  # Target: everything ready (fleet + orchestrator)
  systemd.targets.novax-ready = {
    description = "NovaX Fully Operational";
    after = [ "novax-fleet.target" "novax-orchestrator.service" ];
    wantedBy = [ "multi-user.target" ];
  };

  # ── Path Rewriting Script ───────────────────────────────────────────────
  # On first boot, patch all .nova files to use Linux paths
  systemd.services.novax-path-patcher = {
    description = "NovaX Path Patcher (Windows -> Linux)";
    after = [ "local-fs.target" ];
    before = [ "novax-infra-ready.target" ];
    wantedBy = [ "multi-user.target" ];
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      User = novaxUser;
      ExecStart = pkgs.writeShellScript "novax-patch-paths" ''
        MARKER="${novaxRoot}/.paths-patched"
        if [ -f "$MARKER" ]; then
          echo "Paths already patched, skipping."
          exit 0
        fi

        echo "Patching Windows paths to Linux paths..."

        # Patch novalang.exe -> novalang (the Nix binary is in PATH)
        find ${novaxRoot} -name '*.nova' -exec \
          ${pkgs.gnused}/bin/sed -i \
            -e 's|C:\\\\NovaX\\\\novalang\.exe|${novalangBin}|g' \
            -e 's|C:/NovaX/novalang\.exe|${novalangBin}|g' \
            -e 's|C:\\\\NovaX|${novaxRoot}|g' \
            -e 's|C:/NovaX|${novaxRoot}|g' \
            {} \;

        # Patch Python files too
        find ${novaxRoot} -name '*.py' -exec \
          ${pkgs.gnused}/bin/sed -i \
            -e 's|C:\\\\NovaX|${novaxRoot}|g' \
            -e 's|C:/NovaX|${novaxRoot}|g' \
            -e "s|C:\\\\\\\\NovaX|${novaxRoot}|g" \
            {} \;

        # Patch cloud_config.json
        if [ -f "${novaxRoot}/cloud_config.json" ]; then
          ${pkgs.gnused}/bin/sed -i \
            -e 's|C:\\\\NovaX|${novaxRoot}|g' \
            -e 's|C:/NovaX|${novaxRoot}|g' \
            "${novaxRoot}/cloud_config.json"
        fi

        touch "$MARKER"
        echo "Path patching complete."
      '';
    };
  };

  # ── Static File Server (First — serves dashboard immediately) ───────────
  systemd.services.novax-static = mkNovaService {
    name = "static";
    file = "nova_static_server.nova";
    port = 8888;
    after = [ "novax-path-patcher.service" ];
    wantedBy = [ "novax-fleet.target" ];
  };

  # ══════════════════════════════════════════════════════════════════════════
  # NOVALANG MICROSERVICE FLEET — 86 services
  # ══════════════════════════════════════════════════════════════════════════

  # ── Tier 1: Core Infrastructure (boot first) ────────────────────────────
  systemd.services.novax-tspin = mkNovaService {
    name = "tspin";
    file = "nova_tspin_service.nova";
    port = 9970;
  };

  systemd.services.novax-tscale = mkNovaService {
    name = "tscale";
    file = "nova_tscale_service.nova";
    port = 9986;
  };

  systemd.services.novax-tshield = mkNovaService {
    name = "tshield";
    file = "nova_tshield_service.nova";
    port = 9987;
  };

  systemd.services.novax-thunter = mkNovaService {
    name = "thunter";
    file = "nova_thunter_service.nova";
    port = 9988;
  };

  # ── Tier 2: Execution & Routing ─────────────────────────────────────────
  systemd.services.novax-exec-server = mkNovaService {
    name = "exec-server";
    file = "launchers/exec_server.nova";
    port = 9877;
  };

  systemd.services.novax-cloud-router = mkNovaService {
    name = "cloud-router";
    file = "nova_cloud_router_service.nova";
    port = 9878;
  };

  systemd.services.novax-brain = mkNovaService {
    name = "brain";
    file = "core/server.nova";
    port = 9990;
  };

  systemd.services.novax-vpn-core = mkNovaService {
    name = "vpn-core";
    file = "nova_vpn_core_service.nova";
    port = 9880;
  };

  # ── Tier 3: AI Core (Hivemind, Nexus, STT) ──────────────────────────────
  systemd.services.novax-hivemind = mkNovaService {
    name = "hivemind";
    file = "nova_hivemind_service.nova";
    port = 9881;
  };

  systemd.services.novax-nexus = mkNovaService {
    name = "nexus";
    file = "nova_nexus_service.nova";
    port = 9882;
  };

  systemd.services.novax-stt = mkNovaService {
    name = "stt";
    file = "nova_stt_service.nova";
    port = 9875;
  };

  systemd.services.novax-websocket = mkNovaService {
    name = "websocket";
    file = "ws_server_standalone.nova";
    port = 9998;
  };

  # ── Tier 4: Ternary Engine ──────────────────────────────────────────────
  systemd.services.novax-ternary-server = mkNovaService {
    name = "ternary-server";
    file = "nova_ternary_server_service.nova";
    port = 9885;
  };

  systemd.services.novax-nova-cli = mkNovaService {
    name = "nova-cli";
    file = "nova_cli_server_service.nova";
    port = 9961;
  };

  systemd.services.novax-closed-loop = mkNovaService {
    name = "closed-loop";
    file = "nova_closed_loop_service.nova";
    port = 9888;
  };

  systemd.services.novax-max-patch = mkNovaService {
    name = "max-patch";
    file = "nova_max_patch_service.nova";
    port = 9889;
  };

  systemd.services.novax-tshell = mkNovaService {
    name = "tshell";
    file = "nova_tshell_service.nova";
    port = 9890;
  };

  systemd.services.novax-cortex = mkNovaService {
    name = "cortex";
    file = "nova_cortex_service.nova";
    port = 9896;
  };

  systemd.services.novax-tfetch = mkNovaService {
    name = "tfetch";
    file = "nova_tfetch_service.nova";
    port = 9897;
  };

  # ── Tier 5: Tools & Storage ─────────────────────────────────────────────
  systemd.services.novax-tools = mkNovaService {
    name = "tools";
    file = "nova_tools_service.nova";
    port = 9891;
  };

  systemd.services.novax-vault = mkNovaService {
    name = "vault";
    file = "nova_vault_service.nova";
    port = 9892;
  };

  systemd.services.novax-deepstorage = mkNovaService {
    name = "deepstorage";
    file = "nova_deepstorage_service.nova";
    port = 9893;
  };

  systemd.services.novax-ttools = mkNovaService {
    name = "ttools";
    file = "nova_ternary_tools_service.nova";
    port = 9894;
  };

  systemd.services.novax-tspeak = mkNovaService {
    name = "tspeak";
    file = "nova_tspeak_service.nova";
    port = 9895;
  };

  systemd.services.novax-tkill = mkNovaService {
    name = "tkill";
    file = "nova_tkill_service.nova";
    port = 9901;
  };

  systemd.services.novax-tbuffer = mkNovaService {
    name = "tbuffer";
    file = "nova_tbuffer_service.nova";
    port = 9886;
  };

  systemd.services.novax-skiptrace = mkNovaService {
    name = "skiptrace";
    file = "nova_skiptrace_service.nova";
    port = 9903;
  };

  # ── Tier 6: System Monitoring & Networking ──────────────────────────────
  systemd.services.novax-tsysmon = mkNovaService {
    name = "tsysmon";
    file = "nova_tsysmon_service.nova";
    port = 9905;
  };

  systemd.services.novax-tnet = mkNovaService {
    name = "tnet";
    file = "nova_tnet_service.nova";
    port = 9906;
  };

  systemd.services.novax-tsecurity = mkNovaService {
    name = "tsecurity";
    file = "nova_tsecurity_service.nova";
    port = 9907;
  };

  systemd.services.novax-tmedia = mkNovaService {
    name = "tmedia";
    file = "nova_tmedia_service.nova";
    port = 9908;
  };

  systemd.services.novax-tbuild = mkNovaService {
    name = "tbuild";
    file = "nova_tbuild_service.nova";
    port = 9909;
  };

  systemd.services.novax-tcron = mkNovaService {
    name = "tcron";
    file = "nova_tcron_service.nova";
    port = 9910;
  };

  systemd.services.novax-tquery = mkNovaService {
    name = "tquery";
    file = "nova_tquery_service.nova";
    port = 9911;
  };

  systemd.services.novax-tbus = mkNovaService {
    name = "tbus";
    file = "nova_tbus_service.nova";
    port = 9945;
  };

  systemd.services.novax-tresilience = mkNovaService {
    name = "tresilience";
    file = "nova_tresilience_service.nova";
    port = 9948;
  };

  systemd.services.novax-tintelligence = mkNovaService {
    name = "tintelligence";
    file = "nova_tintelligence_service.nova";
    port = 9924;
  };

  # ── Tier 7: Mesh, Auth, Metrics ─────────────────────────────────────────
  systemd.services.novax-twatch = mkNovaService {
    name = "twatch";
    file = "nova_twatch_service.nova";
    port = 9950;
  };

  systemd.services.novax-tmesh = mkNovaService {
    name = "tmesh";
    file = "nova_tmesh_service.nova";
    port = 9951;
  };

  systemd.services.novax-tauth = mkNovaService {
    name = "tauth";
    file = "nova_tauth_service.nova";
    port = 9952;
  };

  systemd.services.novax-tmetrics = mkNovaService {
    name = "tmetrics";
    file = "nova_tmetrics_service.nova";
    port = 9953;
  };

  systemd.services.novax-tstream = mkNovaService {
    name = "tstream";
    file = "nova_tstream_service.nova";
    port = 9955;
  };

  systemd.services.novax-tcache = mkNovaService {
    name = "tcache";
    file = "nova_tcache_service.nova";
    port = 9956;
  };

  systemd.services.novax-tqueue = mkNovaService {
    name = "tqueue";
    file = "nova_tqueue_service.nova";
    port = 9957;
  };

  systemd.services.novax-tgraph = mkNovaService {
    name = "tgraph";
    file = "nova_tgraph_service.nova";
    port = 9958;
  };

  systemd.services.novax-tscheduler = mkNovaService {
    name = "tscheduler";
    file = "nova_tscheduler_service.nova";
    port = 9959;
  };

  systemd.services.novax-tembed = mkNovaService {
    name = "tembed";
    file = "nova_tembed_service.nova";
    port = 9960;
  };

  # ── Tier 8: Logging, Config, Routing ────────────────────────────────────
  systemd.services.novax-tlog = mkNovaService {
    name = "tlog";
    file = "nova_tlog.nova";
    port = 9942;
  };

  systemd.services.novax-tconfig = mkNovaService {
    name = "tconfig";
    file = "nova_tconfig.nova";
    port = 9941;
  };

  systemd.services.novax-trouter = mkNovaService {
    name = "trouter";
    file = "nova_trouter_service.nova";
    port = 9963;
  };

  systemd.services.novax-tvalidator = mkNovaService {
    name = "tvalidator";
    file = "nova_tvalidator_service.nova";
    port = 9964;
  };

  systemd.services.novax-tsnapshot = mkNovaService {
    name = "tsnapshot";
    file = "nova_tsnapshot_service.nova";
    port = 9965;
  };

  systemd.services.novax-tpipeline = mkNovaService {
    name = "tpipeline";
    file = "nova_tpipeline_service.nova";
    port = 9966;
  };

  systemd.services.novax-tmatrix = mkNovaService {
    name = "tmatrix";
    file = "nova_tmatrix_service.nova";
    port = 9967;
  };

  systemd.services.novax-talchemy = mkNovaService {
    name = "talchemy";
    file = "nova_talchemy_service.nova";
    port = 9928;
  };

  systemd.services.novax-thealth = mkNovaService {
    name = "thealth";
    file = "nova_thealth.nova";
    port = 9940;
  };

  systemd.services.novax-treplay = mkNovaService {
    name = "treplay";
    file = "nova_treplay_service.nova";
    port = 9937;
  };

  # ── Tier 9: Cluster & Compression ──────────────────────────────────────
  systemd.services.novax-tcluster = mkNovaService {
    name = "tcluster";
    file = "nova_tcluster_service.nova";
    port = 9971;
  };

  systemd.services.novax-tcompress = mkNovaService {
    name = "tcompress";
    file = "nova_tcompress_service.nova";
    port = 9972;
  };

  systemd.services.novax-tdiff = mkNovaService {
    name = "tdiff";
    file = "nova_tdiff_service.nova";
    port = 9973;
  };

  systemd.services.novax-taudit = mkNovaService {
    name = "taudit";
    file = "nova_taudit_service.nova";
    port = 9974;
  };

  systemd.services.novax-tnotify = mkNovaService {
    name = "tnotify";
    file = "nova_tnotify_service.nova";
    port = 9975;
  };

  systemd.services.novax-tsync = mkNovaService {
    name = "tsync";
    file = "nova_tsync_service.nova";
    port = 9976;
  };

  systemd.services.novax-tprompt = mkNovaService {
    name = "tprompt";
    file = "nova_tprompt_service.nova";
    port = 9977;
  };

  systemd.services.novax-tmemory = mkNovaService {
    name = "tmemory";
    file = "nova_tmemory_service.nova";
    port = 9978;
  };

  systemd.services.novax-tgateway = mkNovaService {
    name = "tgateway";
    file = "nova_tgateway_service.nova";
    port = 9979;
  };

  systemd.services.novax-tprofile = mkNovaService {
    name = "tprofile";
    file = "nova_tprofile_service.nova";
    port = 9980;
  };

  systemd.services.novax-tlock = mkNovaService {
    name = "tlock";
    file = "nova_tlock_service.nova";
    port = 9981;
  };

  systemd.services.novax-tflow = mkNovaService {
    name = "tflow";
    file = "nova_tflow_service.nova";
    port = 9982;
  };

  systemd.services.novax-tdigest = mkNovaService {
    name = "tdigest";
    file = "nova_tdigest_service.nova";
    port = 9983;
  };

  systemd.services.novax-tbalance = mkNovaService {
    name = "tbalance";
    file = "nova_tbalance_service.nova";
    port = 9984;
  };

  systemd.services.novax-trelay = mkNovaService {
    name = "trelay";
    file = "nova_trelay_service.nova";
    port = 9985;
  };

  # ── Tier 10: Session, Git, Docker, Data ────────────────────────────────
  systemd.services.novax-tsession = mkNovaService {
    name = "tsession";
    file = "nova_tsession_service.nova";
    port = 9912;
  };

  systemd.services.novax-tgit = mkNovaService {
    name = "tgit";
    file = "nova_tgit_service.nova";
    port = 9913;
  };

  systemd.services.novax-tdocker = mkNovaService {
    name = "tdocker";
    file = "nova_tdocker_service.nova";
    port = 9914;
  };

  systemd.services.novax-tterraform = mkNovaService {
    name = "tterraform";
    file = "nova_tterraform_service.nova";
    port = 9915;
  };

  systemd.services.novax-tsqlite = mkNovaService {
    name = "tsqlite";
    file = "nova_tsqlite_service.nova";
    port = 9916;
  };

  systemd.services.novax-tredis = mkNovaService {
    name = "tredis";
    file = "nova_tredis_service.nova";
    port = 9917;
  };

  systemd.services.novax-timage = mkNovaService {
    name = "timage";
    file = "nova_timage_service.nova";
    port = 9918;
  };

  systemd.services.novax-thttp = mkNovaService {
    name = "thttp";
    file = "nova_thttp_service.nova";
    port = 9919;
  };

  systemd.services.novax-tmarkdown = mkNovaService {
    name = "tmarkdown";
    file = "nova_tmarkdown_service.nova";
    port = 9920;
  };

  systemd.services.novax-tyaml = mkNovaService {
    name = "tyaml";
    file = "nova_tyaml_service.nova";
    port = 9921;
  };

  systemd.services.novax-tffmpeg = mkNovaService {
    name = "tffmpeg";
    file = "nova_tffmpeg_service.nova";
    port = 9922;
  };

  systemd.services.novax-ttext = mkNovaService {
    name = "ttext";
    file = "nova_ttext_service.nova";
    port = 9923;
  };

  # ── Tier 11: AI Fleet & Testing ────────────────────────────────────────
  systemd.services.novax-bitnet-fleet = mkNovaService {
    name = "bitnet-fleet";
    file = "nova_bitnet_fleet_service.nova";
    port = 9926;
  };

  systemd.services.novax-tci = mkNovaService {
    name = "tci";
    file = "nova_tci_service.nova";
    port = 9927;
  };

  systemd.services.novax-tconfig2 = mkNovaService {
    name = "tconfig2";
    file = "nova_tconfig_service.nova";
    port = 9932;
  };

  systemd.services.novax-tbenchmark = mkNovaService {
    name = "tbenchmark";
    file = "nova_tbenchmark_service.nova";
    port = 9933;
  };

  systemd.services.novax-ttest = mkNovaService {
    name = "ttest";
    file = "nova_ttest_service.nova";
    port = 9934;
  };

  systemd.services.novax-tdocs = mkNovaService {
    name = "tdocs";
    file = "nova_tdocs_service.nova";
    port = 9935;
  };

  systemd.services.novax-tmicro = mkNovaService {
    name = "tmicro";
    file = "nova_tmicro_service.nova";
    port = 9936;
  };

  # ── Tier 12: System Services ───────────────────────────────────────────
  systemd.services.novax-uia-bridge = mkNovaService {
    name = "uia-bridge";
    file = "nova_uia_bridge_service.nova";
    port = 9902;
  };

  systemd.services.novax-sentinel = mkNovaService {
    name = "sentinel";
    file = "nova_sentinel_service.nova";
    port = 9884;
  };

  systemd.services.novax-tdebug = mkNovaService {
    name = "tdebug";
    file = "nova_tdebug_service.nova";
    port = 9992;
  };

  systemd.services.novax-tmapper = mkNovaService {
    name = "tmapper";
    file = "nova_tmapper_service.nova";
    port = 9994;
  };

  systemd.services.novax-tpacman = mkNovaService {
    name = "tpacman";
    file = "nova_tpacman_service.nova";
    port = 9991;
  };

  systemd.services.novax-ttimeout = mkNovaService {
    name = "ttimeout";
    file = "nova_ttimeout_service.nova";
    port = 9995;
  };

  systemd.services.novax-audit = mkNovaService {
    name = "audit";
    file = "nova_audit_engine.nova";
    port = 9938;
  };

  systemd.services.novax-research = mkNovaService {
    name = "research";
    file = "nova_deep_research_service.nova";
    port = 9939;
  };

  systemd.services.novax-selector = mkNovaService {
    name = "selector";
    file = "nova_model_selector_service.nova";
    port = 9931;
  };

  # ── Tier 13: NovaX LLM ────────────────────────────────────────────────
  systemd.services.novax-llm = mkNovaService {
    name = "llm";
    file = "nova_llm/inference.nova";
    port = 9800;
  };

  systemd.services.novax-quantizer = mkNovaService {
    name = "quantizer";
    file = "nova_quantizer_service.nova";
    port = 9802;
  };

  # ══════════════════════════════════════════════════════════════════════════
  # PYTHON SERVICES — 4 services that remain Python
  # ══════════════════════════════════════════════════════════════════════════

  systemd.services.novax-voice-server = mkPythonService {
    name = "voice-server";
    file = "nova_voice_server.py";
    port = 9801;
  };

  systemd.services.novax-digital-twin = mkPythonService {
    name = "digital-twin";
    file = "nova_digital_twin.py";
    port = 9946;
  };

  systemd.services.novax-dream-mode = mkPythonService {
    name = "dream-mode";
    file = "nova_dream_mode.py";
    port = 9947;
  };

  systemd.services.novax-knowledge-graph = mkPythonService {
    name = "knowledge-graph";
    file = "nova_knowledge_graph.py";
    port = 9949;
  };

  # ══════════════════════════════════════════════════════════════════════════
  # ORCHESTRATOR — Boots LAST, after all fleet services
  # ══════════════════════════════════════════════════════════════════════════
  # The orchestrator uses boot_orchestrator.py which loads core/*.pyc modules
  # and starts the Flask/SocketIO gateway on port 9999.
  systemd.services.novax-orchestrator = {
    description = "NovaX Orchestrator (port 9999)";
    after = [
      "novax-fleet.target"
      "novax-hivemind.service"
      "novax-ternary-server.service"
      "novax-cloud-router.service"
      "novax-static.service"
    ];
    wants = [ "novax-fleet.target" ];
    wantedBy = [ "multi-user.target" ];
    environment = {
      NOVAX_ROOT = novaxRoot;
      PYTHONPATH = "${novaxRoot}:${novaxRoot}/core:${novaxRoot}/lib";
      NOVAX_HOST = "127.0.0.1";
      HOME = "/home/${novaxUser}";
      CUDA_VISIBLE_DEVICES = "0";
    };
    serviceConfig = {
      Type = "simple";
      ExecStartPre = pkgs.writeShellScript "wait-for-redis" ''
        for i in $(seq 1 30); do
          ${pkgs.redis}/bin/redis-cli -h 127.0.0.1 ping 2>/dev/null | grep -q PONG && exit 0
          sleep 0.5
        done
        echo "WARNING: Redis not responding after 15s, starting anyway"
      '';
      ExecStart = "${novaxPython}/bin/python ${novaxRoot}/boot_orchestrator.py";
      WorkingDirectory = novaxRoot;
      User = novaxUser;
      Group = "users";
      Restart = "on-failure";
      RestartSec = 3;
      StartLimitBurst = 5;
      StartLimitIntervalSec = 120;
      StandardInput = "null";
      StandardOutput = "journal";
      StandardError = "journal";
      LimitNOFILE = 65536;
      SyslogIdentifier = "novax-orchestrator";
    };
  };

  # ══════════════════════════════════════════════════════════════════════════
  # NODE.JS GATEWAY (for nova_ai_gateway.js)
  # ══════════════════════════════════════════════════════════════════════════
  systemd.services.novax-ai-gateway = {
    description = "NovaX AI Gateway (Node.js)";
    after = [ "novax-infra-ready.target" ];
    wantedBy = [ "novax-fleet.target" ];
    environment = {
      NOVAX_ROOT = novaxRoot;
      NODE_ENV = "production";
      HOME = "/home/${novaxUser}";
    };
    serviceConfig = {
      Type = "simple";
      ExecStart = "${pkgs.nodejs_22}/bin/node ${novaxRoot}/nova_ai_gateway.js";
      WorkingDirectory = novaxRoot;
      User = novaxUser;
      Group = "users";
      Restart = "on-failure";
      RestartSec = 2;
      StandardInput = "null";
      StandardOutput = "journal";
      StandardError = "journal";
      LimitNOFILE = 65536;
      SyslogIdentifier = "novax-ai-gateway";
    };
  };
}
