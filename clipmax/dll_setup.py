import os
import sys
import site

def setup_cuda_dll_paths() -> None:
    if sys.platform == "win32":
        bases = []
        try:
            bases.extend(site.getsitepackages())
        except Exception:
            pass
        venv_sp = os.path.join(sys.prefix, "Lib", "site-packages")
        if venv_sp not in bases:
            bases.append(venv_sp)

        for base in bases:
            for sub in [("nvidia", "cublas", "bin"), ("nvidia", "cudnn", "bin"), ("nvidia", "cuda_nvrtc", "bin")]:
                p = os.path.join(base, *sub)
                if os.path.exists(p):
                    if hasattr(os, "add_dll_directory"):
                        try:
                            os.add_dll_directory(p)
                        except Exception:
                            pass
                    os.environ["PATH"] = p + os.pathsep + os.environ.get("PATH", "")
