from huggingface_hub import list_models, model_info

try:
    # Check specifically for LFM models to see architectures
    print("Checking LiquidAI models...")
    models = list(list_models(search="liquidai"))
    lfm_models = [m for m in models if "lfm" in m.id.lower()]

    for m in lfm_models:
        try:
            info = model_info(m.id)
            arch = info.config.get("architectures", ["Unknown"])
            print(f"ID: {m.id} | Arch: {arch}")
        except Exception:
            print(f"ID: {m.id} | Arch: Error reading config")

    # Also check if user meant a different model name if 2.6B doesn't show
    # The user said "LFM2-2.6B", looking for similarities.
except Exception as e:
    print(f"Global Error: {e}")
