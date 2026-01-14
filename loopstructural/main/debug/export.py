import pickle
from pathlib import Path
from typing import Any, Dict


def export_debug_package(
    debug_manager,
    m2l_object,
    runner_script_name: str = "run_debug_model.py",
    params: Dict[str, Any] = {},
):

    exported: Dict[str, str] = {}
    if not debug_manager or not getattr(debug_manager, "is_debug", lambda: False)():
        return exported
    # store the m2l object (calculator/sampler etc) and the parameters used
    # in its main function e.g. compute(), sample() etc
    # these will be pickled and saved to the debug directory
    # with the prefix of the runner script name to avoid name clashes
    # e.g. run_debug_model_m2l_object.pkl, run_debug_model_parameters.pkl
    pickles = {'m2l_object': m2l_object, 'params': params}

    if pickles:
        for name, obj in pickles.items():
            pkl_name = f"{runner_script_name.replace('.py', '')}_{name}.pkl"
            try:
                debug_manager.save_debug_file(pkl_name, pickle.dumps(obj))
                exported[name] = pkl_name
            except Exception as e:
                debug_manager.logger(f"Failed to save debug file '{pkl_name}': {e}")
    with open(Path(__file__).parent / 'template.txt', 'r') as f:
        template = f.read()
        template = template.format(runner_name=runner_script_name.replace('.py', ''))

    debug_manager.save_debug_file(runner_script_name, template.encode("utf-8"))
    debug_manager.logger(f"Exported debug package with runner script '{runner_script_name}'")
    return exported
