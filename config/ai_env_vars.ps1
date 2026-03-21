# ============================================================================
# NovaX AI Workload Environment Variables - DEFINITIVE LIST
# Windows 11 | Python | Ollama | CUDA | Rust | PyTorch | HuggingFace | ONNX
# Generated: 2026-03-15
# ============================================================================
# USAGE: dot-source this file in PowerShell:  . .\ai_env_vars.ps1
# Or run: powershell -ExecutionPolicy Bypass -File ai_env_vars.ps1
# To make permanent: run with -Persist flag or use setx manually
# ============================================================================

$AI_ENV_VARS = @{

    # ========================================================================
    # CATEGORY 1: CUDA (Not Already Set)
    # ========================================================================

    "CUDA_LAUNCH_BLOCKING" = @{
        Value       = "0"
        Description = "Forces synchronous CUDA kernel launches when set to 1. Useful for debugging but kills performance. Keep 0 for production."
        Impact      = "CRITICAL for debugging; setting to 1 serializes ALL GPU ops, 10-50x slower. Keep 0."
    }

    "CUDA_DEVICE_ORDER" = @{
        Value       = "PCI_BUS_ID"
        Description = "Controls GPU enumeration order. PCI_BUS_ID matches nvidia-smi ordering."
        Impact      = "LOW direct perf impact but prevents wrong-GPU scheduling. Essential for multi-GPU."
    }

    "CUDA_FORCE_PTX_JIT" = @{
        Value       = "0"
        Description = "When 1, forces JIT compilation from PTX ignoring embedded CUBIN. Increases load time."
        Impact      = "Keep 0. Setting to 1 adds seconds to kernel load for forward-compat testing only."
    }

    "CUDA_DISABLE_PTX_JIT" = @{
        Value       = "0"
        Description = "Disables PTX JIT compilation, requires pre-compiled CUBIN for target arch."
        Impact      = "Keep 0 unless you know all kernels have native CUBIN for your GPU arch."
    }

    "CUDA_CACHE_DISABLE" = @{
        Value       = "0"
        Description = "Disables caching of JIT-compiled kernels when set to 1. Keep 0 for faster subsequent launches."
        Impact      = "MEDIUM. Disabling cache means recompiling PTX every launch. Keep 0."
    }

    "CUDA_CACHE_PATH" = @{
        Value       = "C:\Users\Jupit\AppData\Local\NVIDIA\ComputeCache"
        Description = "Directory for JIT compilation cache. Put on fast SSD."
        Impact      = "LOW-MEDIUM. Fast SSD path reduces JIT cache read/write latency."
    }

    "CUDA_MANAGED_FORCE_DEVICE_ALLOC" = @{
        Value       = "1"
        Description = "Forces managed memory allocations to reside on device. Reduces page faults."
        Impact      = "MEDIUM. Prevents CPU-GPU page migration overhead for unified memory workloads."
    }

    "CUDA_MPS_PIPE_DIRECTORY" = @{
        Value       = ""
        Description = "Directory for CUDA Multi-Process Service pipes. Set if running multiple CUDA processes sharing GPU."
        Impact      = "Only relevant for MPS. Enables concurrent kernel execution from multiple processes."
    }

    "CUDA_COREDUMP_FILE" = @{
        Value       = ""
        Description = "Path for GPU coredump files. Leave empty for production; set for debugging GPU crashes."
        Impact      = "NONE for perf. Debugging only."
    }

    # ========================================================================
    # CATEGORY 2: cuDNN
    # ========================================================================

    "CUDNN_LOGINFO_DBG" = @{
        Value       = "0"
        Description = "Enables cuDNN API logging. Set to 1 for debugging convolution selection."
        Impact      = "Keep 0. Logging adds overhead. Use only for algorithm selection debugging."
    }

    "CUDNN_RESCALE_THRESHOLD" = @{
        Value       = "8"
        Description = "Controls rescaling optimization threshold in cuDNN 9.x. Higher = more aggressive rescaling."
        Impact      = "LOW-MEDIUM. Default 8 is optimal. Lowering to 0 disables optimization."
    }

    "CUDNN_USE_EX2_EMULATION" = @{
        Value       = "1"
        Description = "Enables EX2 emulation optimization in cuDNN 9.x runtime fusion engine."
        Impact      = "LOW. Default 1 enables optimization. Set 0 only if numerical issues arise."
    }

    "CUDNN_LIB_CONFIG" = @{
        Value       = ""
        Description = "Runtime config: JIT or FULL. Auto-detected in cuDNN 9.x. Leave empty."
        Impact      = "NONE if auto-detected. Only set to JIT if you installed cuDNN JIT package only."
    }

    # ========================================================================
    # CATEGORY 3: TensorRT (via ONNX Runtime)
    # ========================================================================

    "ORT_TENSORRT_MAX_WORKSPACE_SIZE" = @{
        Value       = "4294967296"
        Description = "Max GPU memory (bytes) TensorRT can use for workspace. 4GB default. Increase for large models."
        Impact      = "HIGH. More workspace = more optimization opportunities. Set to 50-75% free VRAM."
    }

    "ORT_TENSORRT_ENGINE_CACHE_ENABLE" = @{
        Value       = "1"
        Description = "Cache TensorRT engines to disk. Eliminates rebuild time on subsequent runs."
        Impact      = "HIGH. First run builds engine (minutes). Cached runs load in seconds."
    }

    "ORT_TENSORRT_CACHE_PATH" = @{
        Value       = "C:\NovaX\cache\tensorrt"
        Description = "Path for cached TensorRT engines and INT8 calibration tables."
        Impact      = "MEDIUM. Fast SSD path reduces engine load time."
    }

    "ORT_TENSORRT_FP16_ENABLE" = @{
        Value       = "1"
        Description = "Enable FP16 precision for TensorRT inference. 2x throughput on most GPUs."
        Impact      = "HIGH. Nearly 2x speedup with minimal accuracy loss on Ampere/Ada GPUs."
    }

    "ORT_TENSORRT_INT8_ENABLE" = @{
        Value       = "0"
        Description = "Enable INT8 quantized inference. Requires calibration data. 4x potential speedup."
        Impact      = "VERY HIGH if calibrated properly. 2-4x over FP16. Needs calibration table."
    }

    "ORT_TENSORRT_MAX_PARTITION_ITERATIONS" = @{
        Value       = "1000"
        Description = "Max iterations for TensorRT graph partitioning. More = better optimization, longer build."
        Impact      = "MEDIUM. Higher values improve engine quality at cost of build time."
    }

    "ORT_TENSORRT_MIN_SUBGRAPH_SIZE" = @{
        Value       = "1"
        Description = "Minimum number of nodes in a subgraph for TensorRT to optimize. Lower = more TRT coverage."
        Impact      = "MEDIUM. Default 1 maximizes TRT usage. Increase if small subgraphs cause overhead."
    }

    "ORT_TENSORRT_FORCE_SEQUENTIAL_ENGINE_BUILD" = @{
        Value       = "0"
        Description = "Sequential TRT engine builds in multi-GPU. Set 1 to reduce peak memory during build."
        Impact      = "LOW. Only relevant for multi-GPU ONNX Runtime deployments."
    }

    "ORT_TENSORRT_CONTEXT_MEMORY_SHARING_ENABLE" = @{
        Value       = "1"
        Description = "Share execution context memory between TRT subgraphs. Reduces VRAM usage."
        Impact      = "MEDIUM. Saves VRAM when model has multiple TRT subgraphs."
    }

    "ORT_TENSORRT_DUMP_SUBGRAPHS" = @{
        Value       = "0"
        Description = "Dump TRT subgraphs to disk as ONNX files for debugging."
        Impact      = "NONE for perf. Debugging only."
    }

    # ========================================================================
    # CATEGORY 4: PyTorch
    # ========================================================================

    "PYTORCH_CUDA_ALLOC_CONF" = @{
        Value       = "expandable_segments:True,garbage_collection_threshold:0.8,max_split_size_mb:512"
        Description = "CUDA memory allocator config. expandable_segments reduces fragmentation. GC threshold triggers cleanup at 80% usage. max_split prevents oversized block splits."
        Impact      = "HIGH. Prevents OOM errors, reduces fragmentation by 30-60%. Essential for large models."
    }

    "TORCH_CUDNN_V8_API_ENABLED" = @{
        Value       = "1"
        Description = "Enable cuDNN v8 API for convolutions. Better algorithm selection and fusion."
        Impact      = "MEDIUM. 5-15% speedup on convolution-heavy models (CNNs, image generation)."
    }

    "PYTORCH_NO_CUDA_MEMORY_CACHING" = @{
        Value       = "0"
        Description = "Disables PyTorch CUDA memory caching allocator when 1. Keep 0."
        Impact      = "CRITICAL. Setting to 1 makes every allocation go through cudaMalloc. 10-100x slower."
    }

    "TORCH_SHOW_CPP_STACKTRACES" = @{
        Value       = "0"
        Description = "Show C++ stack traces on errors. Set 1 for debugging."
        Impact      = "NONE for perf. Keep 0 in production."
    }

    "TORCH_LOGS" = @{
        Value       = ""
        Description = "Logging for torch.compile. Set to 'dynamo,aot,inductor' for debugging compilation. Empty for production."
        Impact      = "NONE when empty. Set for debugging torch.compile issues only."
    }

    "TORCHDYNAMO_VERBOSE" = @{
        Value       = "0"
        Description = "Verbose mode for TorchDynamo (torch.compile). Full stack traces on warnings/errors."
        Impact      = "NONE for perf. Debugging torch.compile only."
    }

    "TORCHDYNAMO_REPRO_LEVEL" = @{
        Value       = "0"
        Description = "Reproducibility debugging level for torch.compile. Set 4 for numerical accuracy debugging."
        Impact      = "NONE for perf. Set 2-4 only when debugging accuracy issues."
    }

    "TORCH_LINALG_PREFER_CUSOLVER" = @{
        Value       = "1"
        Description = "Prefer cuSOLVER for linear algebra ops. Better for batched and large matrix operations."
        Impact      = "LOW-MEDIUM. cuSOLVER can be faster than cuBLAS for certain linalg ops."
    }

    "PYTORCH_JIT" = @{
        Value       = "1"
        Description = "Enable PyTorch JIT compiler. Set 0 to disable TorchScript JIT."
        Impact      = "MEDIUM. Keep 1. Disabling breaks torch.jit.script functionality."
    }

    "PYTORCH_ENABLE_MPS_FALLBACK" = @{
        Value       = "0"
        Description = "Enable CPU fallback for unsupported MPS ops (Apple Silicon only). N/A for NVIDIA."
        Impact      = "NONE on NVIDIA. Only relevant for Apple M-series GPUs."
    }

    # ========================================================================
    # CATEGORY 5: ONNX Runtime
    # ========================================================================

    "ORT_LOG_LEVEL" = @{
        Value       = "WARNING"
        Description = "ONNX Runtime log level: VERBOSE, INFO, WARNING, ERROR, FATAL."
        Impact      = "LOW. VERBOSE adds logging overhead. WARNING is good default."
    }

    "OMP_WAIT_POLICY" = @{
        Value       = "ACTIVE"
        Description = "OpenMP thread wait policy for ONNX Runtime. ACTIVE=spin-wait (lower latency). PASSIVE=yield CPU."
        Impact      = "MEDIUM. ACTIVE gives lower latency but uses CPU. PASSIVE if CPU is shared."
    }

    # ========================================================================
    # CATEGORY 6: Python Memory
    # ========================================================================

    "PYTHONMALLOC" = @{
        Value       = "mimalloc"
        Description = "Python memory allocator. Options: malloc, pymalloc, mimalloc. mimalloc is fastest for AI workloads."
        Impact      = "MEDIUM. mimalloc reduces allocation overhead by 10-30% vs default pymalloc. Requires Python 3.13+."
    }

    "PYTHONMALLOCSTATS" = @{
        Value       = "0"
        Description = "Print pymalloc allocator statistics on each arena creation and shutdown."
        Impact      = "NONE for perf. Set 1 for memory debugging only."
    }

    "PYTHONHASHSEED" = @{
        Value       = "0"
        Description = "Fixed hash seed for reproducible dict ordering. 0=random (default). Set fixed int for reproducibility."
        Impact      = "NEGLIGIBLE perf impact. Set fixed value for reproducible ML experiments."
    }

    "PYTHONPROFILEIMPORTTIME" = @{
        Value       = "0"
        Description = "Profile import times when set to 1. Identifies slow imports."
        Impact      = "NONE for perf. Diagnostic tool for startup optimization."
    }

    "MALLOC_TRIM_THRESHOLD_" = @{
        Value       = "65536"
        Description = "glibc: min freed bytes before returning memory to OS. Lower=more aggressive trim. Note trailing underscore."
        Impact      = "MEDIUM on Linux/WSL. Reduces memory bloat in long-running Python processes. N/A native Windows."
    }

    "PYTHONGIL" = @{
        Value       = "1"
        Description = "Python 3.13+ free-threaded builds: set to 0 to disable GIL. Experimental."
        Impact      = "POTENTIALLY HIGH. True parallelism for CPU-bound Python code. Requires free-threaded CPython build."
    }

    # ========================================================================
    # CATEGORY 7: NumPy / SciPy / BLAS
    # ========================================================================

    "NPY_DISABLE_CPU_FEATURES" = @{
        Value       = ""
        Description = "Comma-separated list of SIMD features to disable at runtime (e.g., AVX512F,AVX512_SKX)."
        Impact      = "NEGATIVE if set. Only use to work around specific SIMD bugs. Leave empty."
    }

    "NPY_NUM_BUILD_JOBS" = @{
        Value       = ""
        Description = "Number of parallel jobs for building NumPy from source."
        Impact      = "Build-time only. Set to CPU count for faster NumPy builds."
    }

    "BLIS_NUM_THREADS" = @{
        Value       = ""
        Description = "Thread count for BLIS BLAS backend (used by some NumPy/SciPy builds)."
        Impact      = "MEDIUM if using BLIS. Set to physical core count."
    }

    "SCIPY_USE_PROPACK" = @{
        Value       = "1"
        Description = "Use PROPACK for sparse SVD in SciPy. Faster than ARPACK for some sparse matrices."
        Impact      = "LOW-MEDIUM. Faster sparse SVD for specific workloads."
    }

    # ========================================================================
    # CATEGORY 8: Hugging Face
    # ========================================================================

    "HF_HOME" = @{
        Value       = "C:\NovaX\cache\huggingface"
        Description = "Root directory for all HuggingFace caches (models, datasets, assets). Put on fast SSD."
        Impact      = "MEDIUM. Fast SSD path reduces model load time. Centralizes cache management."
    }

    "HF_HUB_CACHE" = @{
        Value       = "C:\NovaX\cache\huggingface\hub"
        Description = "Where model repos from HuggingFace Hub are cached locally."
        Impact      = "MEDIUM. Same drive as HF_HOME. Avoids re-downloading models."
    }

    "HF_DATASETS_CACHE" = @{
        Value       = "C:\NovaX\cache\huggingface\datasets"
        Description = "Cache directory for HuggingFace datasets."
        Impact      = "LOW-MEDIUM. Prevents re-downloading/re-processing datasets."
    }

    "HF_HUB_OFFLINE" = @{
        Value       = "0"
        Description = "Set 1 for air-gapped/offline operation. All HTTP requests raise OfflineModeIsEnabled."
        Impact      = "LOW. Prevents network calls. Useful for reproducibility and firewalled environments."
    }

    "HF_HUB_DOWNLOAD_TIMEOUT" = @{
        Value       = "30"
        Description = "Seconds to wait for HF Hub server response before falling back to cached files."
        Impact      = "LOW. Higher=more reliable downloads. Lower=faster fallback to cache."
    }

    "HF_DATASETS_IN_MEMORY_MAX_SIZE" = @{
        Value       = "0"
        Description = "Max bytes to load datasets into memory (0=use disk). Set to RAM budget for faster data loading."
        Impact      = "HIGH for training. In-memory datasets eliminate disk I/O bottleneck."
    }

    "HF_TOKEN" = @{
        Value       = ""
        Description = "HuggingFace API token for accessing gated models (Llama, etc). Set via huggingface-cli login."
        Impact      = "NONE for perf. Required for gated model access."
    }

    "TOKENIZERS_PARALLELISM" = @{
        Value       = "true"
        Description = "Enable parallel tokenization in HuggingFace tokenizers. Set false if forking processes."
        Impact      = "MEDIUM. Parallel tokenization is faster but can deadlock with multiprocessing fork."
    }

    "TRANSFORMERS_VERBOSITY" = @{
        Value       = "warning"
        Description = "Logging level for transformers library: debug, info, warning, error, critical."
        Impact      = "LOW. Reduce logging overhead in production."
    }

    "SAFETENSORS_FAST_GPU" = @{
        Value       = "1"
        Description = "Enable fast GPU loading for safetensors format. Direct GPU memory mapping."
        Impact      = "MEDIUM-HIGH. Faster model loading by avoiding CPU->GPU copy."
    }

    # ========================================================================
    # CATEGORY 9: Rust Additional
    # ========================================================================

    "CARGO_INCREMENTAL" = @{
        Value       = "1"
        Description = "Enable incremental compilation. Faster rebuilds at cost of slightly larger binaries."
        Impact      = "HIGH for dev builds. 2-5x faster recompilation. Set 0 for release CI builds."
    }

    "CARGO_ENCODED_RUSTFLAGS" = @{
        Value       = ""
        Description = "Rust 1.55+ replacement for RUSTFLAGS. Unit-separator-delimited flags. Used internally by Cargo."
        Impact      = "Same as RUSTFLAGS. Prefer RUSTFLAGS for manual setting."
    }

    "CARGO_TARGET_DIR" = @{
        Value       = "C:\NovaX\cache\cargo_target"
        Description = "Shared target directory for Cargo builds. Avoids duplicate compilation across projects."
        Impact      = "MEDIUM. Saves disk space and enables shared dependency caching."
    }

    "CARGO_PROFILE_RELEASE_LTO" = @{
        Value       = "true"
        Description = "Enable Link-Time Optimization for release builds. Better inlining across crate boundaries."
        Impact      = "HIGH. 10-20% faster binaries. Build time increases 2-5x."
    }

    "CARGO_PROFILE_RELEASE_CODEGEN_UNITS" = @{
        Value       = "1"
        Description = "Single codegen unit for release builds. Maximum optimization, slower compilation."
        Impact      = "MEDIUM. 5-10% faster binaries. Compile time increases significantly."
    }

    "CARGO_PROFILE_RELEASE_OPT_LEVEL" = @{
        Value       = "3"
        Description = "Maximum optimization level for Rust release builds."
        Impact      = "MEDIUM. Level 3 = aggressive optimization including vectorization."
    }

    "CARGO_REGISTRIES_CRATES_IO_PROTOCOL" = @{
        Value       = "sparse"
        Description = "Use sparse protocol for crates.io registry. Faster dependency resolution."
        Impact      = "LOW. Faster cargo update/build dependency resolution."
    }

    "RUST_BACKTRACE" = @{
        Value       = "0"
        Description = "Show backtraces on panic. Set 1 for debugging, 0 for production."
        Impact      = "NEGLIGIBLE. Keep 0 in production. 1 for debugging."
    }

    "RUST_MIN_STACK" = @{
        Value       = "8388608"
        Description = "Minimum stack size in bytes for Rust threads (default 8MB). Increase for deep recursion."
        Impact      = "LOW. Only increase if hitting stack overflow in recursive algorithms."
    }

    # ========================================================================
    # CATEGORY 10: Windows-Specific Performance
    # ========================================================================

    "GPU_MAX_HEAP_SIZE" = @{
        Value       = "100"
        Description = "Max GPU heap size as percentage. 100=use all available GPU heap memory."
        Impact      = "MEDIUM for OpenCL workloads. Allows full GPU memory utilization."
    }

    "GPU_MAX_ALLOC_PERCENT" = @{
        Value       = "100"
        Description = "Max single allocation as percentage of GPU memory."
        Impact      = "LOW. Prevents artificially limited allocations."
    }

    "PROCESSOR_ARCHITECTURE" = @{
        Value       = "AMD64"
        Description = "System processor architecture. Set by Windows. Do not modify."
        Impact      = "NONE. Read-only system variable."
    }

    "TEMP" = @{
        Value       = "C:\NovaX\temp"
        Description = "Temporary file directory. Put on fast SSD/NVMe for better I/O during model operations."
        Impact      = "LOW-MEDIUM. Fast temp storage helps with model downloading, extraction, compilation."
    }

    "TMP" = @{
        Value       = "C:\NovaX\temp"
        Description = "Same as TEMP. Some tools use TMP instead."
        Impact      = "Same as TEMP."
    }

    # ========================================================================
    # CATEGORY 11: OpenMP Additional
    # ========================================================================

    "OMP_SCHEDULE" = @{
        Value       = "STATIC"
        Description = "Default loop scheduling: STATIC, DYNAMIC, GUIDED, AUTO. STATIC has lowest overhead."
        Impact      = "MEDIUM. STATIC is best for uniform workloads. DYNAMIC for unbalanced iterations."
    }

    "OMP_DYNAMIC" = @{
        Value       = "FALSE"
        Description = "Allow runtime to dynamically adjust thread count. FALSE=use exact OMP_NUM_THREADS."
        Impact      = "LOW-MEDIUM. FALSE gives predictable threading. TRUE may reduce oversubscription."
    }

    "OMP_PROC_BIND" = @{
        Value       = "CLOSE"
        Description = "Thread binding policy: CLOSE, SPREAD, MASTER, TRUE, FALSE. CLOSE=bind to nearby cores."
        Impact      = "MEDIUM-HIGH. CLOSE reduces cache thrashing. SPREAD maximizes memory bandwidth."
    }

    "OMP_PLACES" = @{
        Value       = "cores"
        Description = "Where to bind threads: threads, cores, sockets, or explicit list."
        Impact      = "MEDIUM. 'cores' binds one thread per physical core, avoiding HT contention."
    }

    "OMP_STACKSIZE" = @{
        Value       = "8M"
        Description = "Stack size for OpenMP threads. Increase for deep recursion or large stack arrays."
        Impact      = "LOW. Only increase if hitting stack overflow in parallel regions."
    }

    "OMP_MAX_ACTIVE_LEVELS" = @{
        Value       = "1"
        Description = "Max nested parallelism depth. 1=no nested parallel regions."
        Impact      = "LOW. Nested parallelism usually hurts. Keep 1."
    }

    "OMP_THREAD_LIMIT" = @{
        Value       = ""
        Description = "Hard upper limit on total OpenMP threads. Empty=no limit beyond OMP_NUM_THREADS."
        Impact      = "MEDIUM. Set to physical core count to prevent oversubscription across libraries."
    }

    "OMP_NESTED" = @{
        Value       = "FALSE"
        Description = "Enable nested parallelism (deprecated, use OMP_MAX_ACTIVE_LEVELS). Keep FALSE."
        Impact      = "NEGATIVE if TRUE. Nested parallelism causes thread explosion."
    }

    # ========================================================================
    # CATEGORY 11b: Intel OpenMP (KMP_*)
    # ========================================================================

    "KMP_AFFINITY" = @{
        Value       = "granularity=fine,compact,1,0"
        Description = "Intel OpenMP thread-to-core binding. compact=bind consecutive threads to nearby cores."
        Impact      = "HIGH. 10-30% speedup for MKL/PyTorch CPU workloads. Reduces cache thrashing."
    }

    "KMP_BLOCKTIME" = @{
        Value       = "1"
        Description = "Ms threads spin-wait after parallel region before sleeping. 0-1 best for CNN inference."
        Impact      = "MEDIUM-HIGH. Default 200ms wastes CPU. 0-1ms frees CPU for other work immediately."
    }

    "KMP_SETTINGS" = @{
        Value       = "1"
        Description = "Print Intel OpenMP settings at startup. Useful for verifying configuration."
        Impact      = "NONE for perf. Set 1 for debugging, 0 for production."
    }

    "KMP_DUPLICATE_LIB_OK" = @{
        Value       = "TRUE"
        Description = "Allow multiple copies of OpenMP runtime. Prevents crash when mixing libiomp5/libgomp."
        Impact      = "NONE for perf. Prevents 'OMP: Error #15' crash. Essential on Windows with conda."
    }

    "KMP_STACKSIZE" = @{
        Value       = "8m"
        Description = "Intel OpenMP thread stack size. Same purpose as OMP_STACKSIZE but Intel-specific."
        Impact      = "LOW. Increase only for deep recursion in parallel code."
    }

    # ========================================================================
    # CATEGORY 12: NCCL (Multi-GPU Communication)
    # ========================================================================

    "NCCL_DEBUG" = @{
        Value       = "WARN"
        Description = "NCCL debug level: VERSION, WARN, INFO, TRACE. WARN for production."
        Impact      = "NONE at WARN. INFO/TRACE add significant logging overhead."
    }

    "NCCL_P2P_DISABLE" = @{
        Value       = "0"
        Description = "Disable peer-to-peer GPU communication via NVLink/PCIe. Keep 0 for best perf."
        Impact      = "HIGH if disabled. P2P is fastest inter-GPU path. Only disable for debugging."
    }

    "NCCL_P2P_LEVEL" = @{
        Value       = ""
        Description = "Max topological distance for P2P: LOC, PIX, PXB, PHB, SYS. Empty=auto-optimal."
        Impact      = "MEDIUM. Auto-detection is usually best. Override only for specific topology issues."
    }

    "NCCL_SHM_DISABLE" = @{
        Value       = "0"
        Description = "Disable shared memory transport between GPUs on same node."
        Impact      = "MEDIUM if disabled. SHM is fast fallback when P2P unavailable."
    }

    "NCCL_BUFFSIZE" = @{
        Value       = "4194304"
        Description = "NCCL buffer size in bytes (default 4MB). Increase for better throughput on large collectives."
        Impact      = "LOW-MEDIUM. Larger buffers improve bandwidth but use more GPU memory."
    }

    "NCCL_NTHREADS" = @{
        Value       = "512"
        Description = "CUDA threads per NCCL block. 512 for modern GPUs, 256 for older."
        Impact      = "LOW. Default is optimized. Reduce if GPU SM occupancy is a concern."
    }

    "NCCL_MAX_NCHANNELS" = @{
        Value       = ""
        Description = "Max NCCL communication channels. Limits CUDA blocks used for communication."
        Impact      = "MEDIUM. Reducing frees SMs for compute. Increasing boosts comm throughput."
    }

    "NCCL_MIN_NCHANNELS" = @{
        Value       = ""
        Description = "Min NCCL communication channels. Increase for better throughput on fast interconnects."
        Impact      = "MEDIUM. Setting higher on NVLink systems can improve collective performance."
    }

    "NCCL_SOCKET_NTHREADS" = @{
        Value       = "2"
        Description = "CPU helper threads per socket connection. Increase for higher socket bandwidth."
        Impact      = "MEDIUM for socket-based multi-node. 2-4 is optimal."
    }

    "NCCL_NSOCKS_PERTHREAD" = @{
        Value       = "4"
        Description = "Sockets per helper thread. Higher helps when per-socket speed is limited."
        Impact      = "MEDIUM for socket transport. 4-8 on cloud instances (AWS/GCP)."
    }

    "NCCL_SOCKET_IFNAME" = @{
        Value       = ""
        Description = "Network interface filter for NCCL. Comma-separated prefixes. ^prefix to exclude."
        Impact      = "HIGH for multi-node. Ensures NCCL uses the right network interface."
    }

    "NCCL_NET_GDR_LEVEL" = @{
        Value       = ""
        Description = "GPU Direct RDMA distance: LOC, PIX, PXB, PHB, SYS. Empty=auto."
        Impact      = "HIGH for RDMA. Controls when GPUDirect bypasses CPU for network I/O."
    }

    "NCCL_NET_GDR_READ" = @{
        Value       = ""
        Description = "Force GPU Direct RDMA for read operations. Empty=auto, 0=disable, 1=force."
        Impact      = "MEDIUM-HIGH for RDMA-capable systems."
    }

    "NCCL_CROSS_NIC" = @{
        Value       = "0"
        Description = "0=same NIC per ring (rail-optimized), 1=allow cross-NIC (single-switch topology)."
        Impact      = "MEDIUM for multi-NIC systems. Match to your network topology."
    }

    "NCCL_IB_TIMEOUT" = @{
        Value       = "14"
        Description = "InfiniBand timeout: 4.096us * 2^value. Increase for large networks."
        Impact      = "LOW. Only adjust for IB timeout issues on large clusters."
    }

    "NCCL_IB_RELAXED_ORDERING" = @{
        Value       = "1"
        Description = "Enable relaxed ordering for IB Verbs. Improves perf in virtualized environments."
        Impact      = "MEDIUM for cloud/virtualized IB. Significant throughput improvement."
    }

    "NCCL_CHECKS_DISABLE" = @{
        Value       = "1"
        Description = "Disable argument validation on each collective call. Reduces per-call latency."
        Impact      = "LOW. Saves microseconds per collective. Enable (0) during development."
    }

    "NCCL_NVLS_ENABLE" = @{
        Value       = "1"
        Description = "Enable NVLink SHARP for all-reduce on NVLink systems. Auto-enabled where supported."
        Impact      = "HIGH on NVLink systems. Significant all-reduce throughput improvement."
    }

    "NCCL_GDRCOPY_ENABLE" = @{
        Value       = "1"
        Description = "Enable GDRCopy for improved small-message latency with GPU Direct RDMA."
        Impact      = "MEDIUM. Better latency for small collectives on RDMA-capable systems."
    }

    # ========================================================================
    # CATEGORY 13: Triton (OpenAI Triton Compiler)
    # ========================================================================

    "TRITON_CACHE_DIR" = @{
        Value       = "C:\NovaX\cache\triton"
        Description = "Directory for Triton kernel compilation cache. Fast SSD recommended."
        Impact      = "MEDIUM. Cached kernels avoid recompilation. Major speedup on subsequent runs."
    }

    "TRITON_PRINT_AUTOTUNING" = @{
        Value       = "0"
        Description = "Print autotuning results for Triton kernels. Set 1 for debugging."
        Impact      = "NONE for perf. Debugging only."
    }

    "TRITON_INTERPRET" = @{
        Value       = "0"
        Description = "Run Triton kernels in interpreter mode (CPU). For debugging only."
        Impact      = "CRITICAL. Setting 1 runs GPU kernels on CPU. Orders of magnitude slower."
    }

    # ========================================================================
    # CATEGORY 14: Other AI/ML Frameworks
    # ========================================================================

    # --- Ollama (not already listed) ---

    "OLLAMA_HOST" = @{
        Value       = "127.0.0.1:11434"
        Description = "Ollama server bind address and port."
        Impact      = "NONE for perf. Network configuration only."
    }

    "OLLAMA_MODELS" = @{
        Value       = "C:\NovaX\models\ollama"
        Description = "Directory for Ollama model storage. Put on fast NVMe for faster model loading."
        Impact      = "MEDIUM. Fast storage reduces model load time significantly."
    }

    "OLLAMA_SCHED_SPREAD" = @{
        Value       = "false"
        Description = "Spread model layers across all GPUs instead of packing onto fewest GPUs."
        Impact      = "MEDIUM for multi-GPU. Spreading increases memory bandwidth but adds inter-GPU comm."
    }

    "OLLAMA_TMPDIR" = @{
        Value       = "C:\NovaX\temp\ollama"
        Description = "Temporary directory for Ollama operations."
        Impact      = "LOW. Fast SSD path helps with temporary file operations."
    }

    "OLLAMA_DEBUG" = @{
        Value       = "0"
        Description = "Enable debug logging for Ollama server."
        Impact      = "NONE for perf. Debugging only."
    }

    "OLLAMA_CONTEXT_LENGTH" = @{
        Value       = ""
        Description = "Override default context length. Empty=auto (4k/32k/256k based on VRAM)."
        Impact      = "HIGH. Larger context uses more VRAM and is slower. Match to your use case."
    }

    "OLLAMA_VULKAN" = @{
        Value       = "0"
        Description = "Enable Vulkan backend for GPU inference (alternative to CUDA)."
        Impact      = "LOW. CUDA is faster on NVIDIA. Vulkan useful for AMD/Intel GPUs."
    }

    # --- llama.cpp / GGML ---

    "GGML_VK_VISIBLE_DEVICES" = @{
        Value       = ""
        Description = "Vulkan device visibility for GGML. Empty=all devices."
        Impact      = "LOW. Only relevant for Vulkan backend GPU selection."
    }

    "GGML_CUDA_NO_PINNED" = @{
        Value       = "0"
        Description = "Disable CUDA pinned memory. Keep 0 for best CPU-GPU transfer speed."
        Impact      = "MEDIUM. Pinned memory enables async transfers. Disabling slows data movement."
    }

    # --- vLLM ---

    "VLLM_USE_V1" = @{
        Value       = "1"
        Description = "Enable vLLM v1 engine with improved scheduling and memory management."
        Impact      = "HIGH. v1 engine has better throughput and latency characteristics."
    }

    "VLLM_WORKER_MULTIPROC_METHOD" = @{
        Value       = "spawn"
        Description = "Multiprocessing method for vLLM workers. spawn is safer on Windows."
        Impact      = "LOW. spawn avoids fork-related issues on Windows."
    }

    # --- TensorFlow (if used) ---

    "TF_CPP_MIN_LOG_LEVEL" = @{
        Value       = "2"
        Description = "TensorFlow C++ log level. 0=all, 1=no INFO, 2=no WARNING, 3=no ERROR."
        Impact      = "LOW. Reduces console spam. 2 suppresses warnings."
    }

    "TF_FORCE_GPU_ALLOW_GROWTH" = @{
        Value       = "true"
        Description = "Allow TensorFlow GPU memory to grow incrementally instead of pre-allocating all VRAM."
        Impact      = "MEDIUM. Prevents TF from grabbing all VRAM. Essential when running alongside Ollama."
    }

    "TF_GPU_THREAD_MODE" = @{
        Value       = "gpu_private"
        Description = "Thread mode for TF GPU ops: global, gpu_private, gpu_shared."
        Impact      = "MEDIUM. gpu_private gives each GPU its own thread pool, reducing contention."
    }

    "TF_ENABLE_ONEDNN_OPTS" = @{
        Value       = "1"
        Description = "Enable oneDNN (MKL-DNN) optimizations for TensorFlow CPU ops."
        Impact      = "MEDIUM-HIGH for CPU inference. 10-30% speedup on Intel CPUs."
    }

    "TF_XLA_FLAGS" = @{
        Value       = ""
        Description = "XLA compiler flags for TensorFlow. Set '--tf_xla_auto_jit=2' for auto-compilation."
        Impact      = "HIGH when enabled. XLA can fuse ops and optimize memory for 20-50% speedup."
    }

    # --- JAX ---

    "JAX_PLATFORM_NAME" = @{
        Value       = "gpu"
        Description = "Default JAX backend: cpu, gpu, tpu."
        Impact      = "HIGH. Ensures JAX uses GPU. Will fall back to CPU if not set."
    }

    "XLA_PYTHON_CLIENT_PREALLOCATE" = @{
        Value       = "false"
        Description = "Disable JAX/XLA GPU memory pre-allocation. Same as TF_FORCE_GPU_ALLOW_GROWTH."
        Impact      = "MEDIUM. Prevents JAX from grabbing all VRAM at startup."
    }

    "XLA_PYTHON_CLIENT_MEM_FRACTION" = @{
        Value       = "0.8"
        Description = "Fraction of GPU memory JAX/XLA can use. 0.8=80%."
        Impact      = "MEDIUM. Limits JAX VRAM to leave room for other GPU processes."
    }

    "XLA_FLAGS" = @{
        Value       = ""
        Description = "XLA compiler flags. --xla_gpu_cuda_data_dir for CUDA path."
        Impact      = "Varies by flag. Can enable fusion and memory optimizations."
    }

    # --- CuPy ---

    "CUPY_TF32" = @{
        Value       = "1"
        Description = "Allow CuPy to use TF32 for 32-bit float ops on Ampere+. 8x tensor core throughput."
        Impact      = "HIGH on Ampere/Ada. Near-FP32 accuracy with FP16-like speed for matmul."
    }

    "CUPY_CUDA_PER_THREAD_DEFAULT_STREAM" = @{
        Value       = "1"
        Description = "Each CPU thread gets its own CUDA stream. Better GPU utilization in multi-threaded code."
        Impact      = "MEDIUM. Enables concurrent kernel execution from different CPU threads."
    }

    "CUPY_ACCELERATORS" = @{
        Value       = "cub"
        Description = "CuPy acceleration backends: cub, cutensor, cutensornet. Priority order."
        Impact      = "MEDIUM. CUB provides faster reductions and scans."
    }

    # --- Numba ---

    "NUMBA_CUDA_DRIVER" = @{
        Value       = ""
        Description = "Path to CUDA driver library. Empty=auto-detect."
        Impact      = "NONE usually. Set only if Numba can't find CUDA driver."
    }

    "NUMBA_ENABLE_CUDASIM" = @{
        Value       = "0"
        Description = "Enable CUDA simulator (run GPU code on CPU). For debugging only."
        Impact      = "CRITICAL. Setting 1 runs GPU code on CPU. Production must be 0."
    }

    "NUMBA_NUM_THREADS" = @{
        Value       = ""
        Description = "Thread count for Numba parallel operations. Empty=auto (CPU count)."
        Impact      = "MEDIUM. Set to physical core count for optimal parallel JIT performance."
    }

    # --- Weights & Biases ---

    "WANDB_MODE" = @{
        Value       = "disabled"
        Description = "W&B logging mode: online, offline, disabled. Disable if not using W&B."
        Impact      = "LOW. Prevents unnecessary network calls and file writes during training."
    }

    "WANDB_SILENT" = @{
        Value       = "true"
        Description = "Suppress W&B console output."
        Impact      = "NEGLIGIBLE. Reduces console noise."
    }

    # --- General ML ---

    "TOKENIZERS_PARALLELISM" = @{
        Value       = "true"
        Description = "Enable parallel tokenization. Set false to avoid deadlock with multiprocessing.fork()."
        Impact      = "MEDIUM. Faster tokenization but can deadlock in forked subprocesses."
    }

    "PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION" = @{
        Value       = "cpp"
        Description = "Use C++ protobuf implementation instead of pure Python. Much faster serialization."
        Impact      = "MEDIUM. 10-50x faster protobuf parsing for ONNX model loading and gRPC."
    }

    "GRPC_POLL_STRATEGY" = @{
        Value       = "epoll1"
        Description = "gRPC polling strategy. epoll1 is most efficient on Linux. poll on Windows."
        Impact      = "LOW-MEDIUM. Better I/O efficiency for gRPC-based model serving."
    }
}

# ============================================================================
# APPLY ALL ENVIRONMENT VARIABLES
# ============================================================================
function Set-AIEnvironment {
    param(
        [switch]$Persist,
        [switch]$DryRun
    )

    foreach ($key in $AI_ENV_VARS.Keys) {
        $entry = $AI_ENV_VARS[$key]
        $value = $entry.Value

        # Skip empty values (user should set these manually)
        if ([string]::IsNullOrEmpty($value)) {
            if ($DryRun) {
                Write-Host "[SKIP] $key = (empty, set manually)" -ForegroundColor DarkGray
            }
            continue
        }

        if ($DryRun) {
            Write-Host "[SET]  $key = $value" -ForegroundColor Cyan
            Write-Host "       Impact: $($entry.Impact)" -ForegroundColor DarkYellow
        } else {
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
            Write-Host "[OK]   $key = $value" -ForegroundColor Green

            if ($Persist) {
                [Environment]::SetEnvironmentVariable($key, $value, "User")
                Write-Host "       (persisted to user env)" -ForegroundColor DarkGreen
            }
        }
    }

    Write-Host ""
    Write-Host "Total variables: $($AI_ENV_VARS.Count)" -ForegroundColor White
    if ($DryRun) {
        Write-Host "DRY RUN - no changes made. Remove -DryRun to apply." -ForegroundColor Yellow
    }
}

# ============================================================================
# PRINT SUMMARY
# ============================================================================
function Show-AIEnvironmentSummary {
    $categories = @{
        "CUDA"          = ($AI_ENV_VARS.Keys | Where-Object { $_ -match "^CUDA_" }).Count
        "cuDNN"         = ($AI_ENV_VARS.Keys | Where-Object { $_ -match "^CUDNN_" }).Count
        "TensorRT/ORT"  = ($AI_ENV_VARS.Keys | Where-Object { $_ -match "^ORT_" }).Count
        "PyTorch"       = ($AI_ENV_VARS.Keys | Where-Object { $_ -match "^(PYTORCH_|TORCH_)" }).Count
        "Python"        = ($AI_ENV_VARS.Keys | Where-Object { $_ -match "^PYTHON" }).Count
        "NumPy/SciPy"   = ($AI_ENV_VARS.Keys | Where-Object { $_ -match "^(NPY_|SCIPY_|BLIS_)" }).Count
        "HuggingFace"   = ($AI_ENV_VARS.Keys | Where-Object { $_ -match "^(HF_|TRANSFORMERS_|TOKENIZERS_|SAFETENSORS_)" }).Count
        "Rust/Cargo"    = ($AI_ENV_VARS.Keys | Where-Object { $_ -match "^(CARGO_|RUST_)" }).Count
        "OpenMP/Intel"  = ($AI_ENV_VARS.Keys | Where-Object { $_ -match "^(OMP_|KMP_)" }).Count
        "NCCL"          = ($AI_ENV_VARS.Keys | Where-Object { $_ -match "^NCCL_" }).Count
        "Triton"        = ($AI_ENV_VARS.Keys | Where-Object { $_ -match "^TRITON_" }).Count
        "Ollama"        = ($AI_ENV_VARS.Keys | Where-Object { $_ -match "^OLLAMA_" }).Count
        "Other ML"      = ($AI_ENV_VARS.Keys | Where-Object { $_ -match "^(TF_|JAX_|XLA_|CUPY_|NUMBA_|WANDB_|VLLM_|GGML_|GRPC_|PROTOCOL_)" }).Count
        "Windows"       = ($AI_ENV_VARS.Keys | Where-Object { $_ -match "^(GPU_|PROCESSOR_|TEMP$|TMP$)" }).Count
    }

    Write-Host "`n=== NovaX AI Environment Variables Summary ===" -ForegroundColor Cyan
    foreach ($cat in $categories.GetEnumerator() | Sort-Object Value -Descending) {
        Write-Host ("  {0,-20} {1,3} vars" -f $cat.Key, $cat.Value) -ForegroundColor White
    }
    Write-Host ("  {0,-20} {1,3} vars" -f "TOTAL", $AI_ENV_VARS.Count) -ForegroundColor Green
    Write-Host ""
}

# ============================================================================
# USAGE
# ============================================================================
Write-Host @"

NovaX AI Environment Variables loaded.
  Total: $($AI_ENV_VARS.Count) variables across 14 categories

Commands:
  Show-AIEnvironmentSummary          # Print category breakdown
  Set-AIEnvironment -DryRun          # Preview what would be set
  Set-AIEnvironment                  # Apply to current session
  Set-AIEnvironment -Persist         # Apply + save permanently

  `$AI_ENV_VARS["CUDA_LAUNCH_BLOCKING"]  # Inspect a specific variable

"@ -ForegroundColor Cyan
