import os
import sys

def setup_cuda_dll_paths() -> None:
    if sys.platform == "win32":
        import site
        candidate_paths = []
        try:
            candidate_paths.extend(site.getsitepackages())
        except Exception:
            pass

        try:
            user_site = site.getusersitepackages()
            if isinstance(user_site, str):
                candidate_paths.append(user_site)
        except Exception:
            pass

        venv_sp = os.path.join(sys.prefix, "Lib", "site-packages")
        candidate_paths.append(venv_sp)

        for p in sys.path:
            if "site-packages" in p:
                candidate_paths.append(p)

        seen = set()
        unique_paths = []
        for p in candidate_paths:
            norm = os.path.normcase(os.path.normpath(p))
            if norm not in seen and os.path.isdir(norm):
                seen.add(norm)
                unique_paths.append(norm)

        for p in unique_paths:
            cublas_dir = os.path.join(p, "nvidia", "cublas", "bin")
            cudnn_dir = os.path.join(p, "nvidia", "cudnn", "bin")
            cuda_nvrtc_dir = os.path.join(p, "nvidia", "cuda_nvrtc", "bin")

            for d in (cublas_dir, cudnn_dir, cuda_nvrtc_dir):
                if os.path.exists(d):
                    if hasattr(os, "add_dll_directory"):
                        try:
                            os.add_dll_directory(d)
                        except Exception:
                            pass
                    os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
