from .structural_engine import get_structural_veto, get_dual_mode_context, apply_structural_veto  # Phase 0 port


def get_model_class(model_name):
    """Lazy import to avoid loading kronos.py at package init (which shadows the kronos/ package)."""
    if model_name == 'structural_veto':
        return get_structural_veto
    # Lazy import for kronos models — deferred to avoid kronos.py sys.path pollution
    if model_name in ('kronos_tokenizer', 'kronos', 'kronos_predictor'):
        from .kronos import KronosTokenizer, Kronos, KronosPredictor
        _map = {
            'kronos_tokenizer': KronosTokenizer,
            'kronos': Kronos,
            'kronos_predictor': KronosPredictor,
        }
        return _map[model_name]
    print(f"Model {model_name} not found in model_dict")
    raise NotImplementedError
