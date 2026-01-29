# Model Provisioning

Vociferous separates provisioning from runtime execution. Use the `vociferous-provision` CLI (`scripts/provision_models.py`) to download or convert models before starting the application.

## Offline / Sideloading

You can provide a local directory as the source for provisioning using `--source-dir`. The directory must have a Transformers model layout compatible with CTranslate2 conversion, typically including:

- `config.json`
- One of `model.safetensors`, `pytorch_model.bin`, or `model.bin`
- (optional) `tokenizer.json`

Example:

```
python scripts/provision_models.py install qwen4b --source-dir /path/to/local/model
```

This will validate the directory and run the conversion step, producing CTranslate2 artifacts under the model cache directory.

For completely air-gapped systems, produce an offline bundle with the above structure and transfer it to the target machine before running the CLI.
