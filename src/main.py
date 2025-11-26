import hydra
from omegaconf import DictConfig
from app import RobotAnimatorApp


@hydra.main(version_base=None, config_path="../config", config_name="config")
def main(cfg: DictConfig):
    app = RobotAnimatorApp(cfg)
    app.run()


if __name__ == "__main__":
    main()
