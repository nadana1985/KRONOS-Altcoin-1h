from .kronos import KronosTokenizer, Kronos, KronosPredictor
from .structural_engine import get_structural_veto, get_dual_mode_context, apply_structural_veto  # Phase 0 port

model_dict = {
    'kronos_tokenizer': KronosTokenizer,
    'kronos': Kronos,
    'kronos_predictor': KronosPredictor,
    'structural_veto': get_structural_veto,  # sovereign dual-mode + veto
}


def get_model_class(model_name):
    if model_name in model_dict:
        return model_dict[model_name]
    else:
        print(f"Model {model_name} not found in model_dict")
        raise NotImplementedError


