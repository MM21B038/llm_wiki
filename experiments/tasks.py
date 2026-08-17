import time

def simulate_heavy_ml_task(model_name, duration):
    print(f"[{model_name}] Training started...")
    time.sleep(duration)
    print(f"[{model_name}] Training finished!")
    return f"Model {model_name} successfully trained in {duration} seconds."
