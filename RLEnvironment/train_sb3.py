from __future__ import annotations

import glob
import os
import time

import supersuit as ss
from stable_baselines3 import PPO
from stable_baselines3.ppo import MlpPolicy
from pettingzoo.utils import parallel_to_aec

from wedding_gossip_env import wedding_gossip_environment_v2


def train_wedding(
    env_fn, steps: int = 10_000, seed: int | None = 0, **env_kwargs
):
    # Train a single model to play as each agent in a cooperative Parallel environment
    env = env_fn.WeddingGossipEnvironment(**env_kwargs)

    env.reset(seed=seed)

    print(f"Starting training on {str(env.metadata['name'])}.")

    env = ss.pettingzoo_env_to_vec_env_v1(env)
    env = ss.concat_vec_envs_v1(env, 8, num_cpus=2, base_class="stable_baselines3")

    file_name = max(
            glob.glob(f"{env.unwrapped.metadata['name']}*.zip"), key=os.path.getctime
    )

    if os.path.exists(file_name):
        print('\nloading checkpoint')
        model = PPO.load(file_name, env=env)
    else:
        model = PPO(
            MlpPolicy,
            env,
            verbose=3,
            learning_rate=1e-3,
            batch_size=256,
        )
        
    model.learn(total_timesteps=steps)

    model.save(f"{env.unwrapped.metadata.get('name')}_{time.strftime('%Y%m%d-%H%M%S')}")

    print("Model has been saved.")

    print(f"Finished training on {str(env.unwrapped.metadata['name'])}.")

    env.close()


def eval(env_fn, num_games: int = 100, render_mode: str | None = None, **env_kwargs):
    # Evaluate a trained agent vs a random agent
    env = env_fn.WeddingGossipEnvironment(render_mode=render_mode, **env_kwargs)
    env = parallel_to_aec(env)

    print(
        f"\nStarting evaluation on {str(env.metadata['name'])} (num_games={num_games}, render_mode={render_mode})"
    )

    try:
        latest_policy = max(
            glob.glob(f"{env.metadata['name']}*.zip"), key=os.path.getctime
        )
    except ValueError:
        print("Policy not found.")
        exit(0)

    model = PPO.load(latest_policy)

    rewards = {agent: 0 for agent in env.possible_agents}

    # Note: We train using the Parallel API but evaluate using the AEC API
    # SB3 models are designed for single-agent settings, we get around this by using he same model for every agent
    for i in range(num_games):
        env.reset(seed=i)

        for agent in env.agent_iter():
            obs, reward, termination, truncation, info = env.last()

            for a in env.agents:
                rewards[a] += env.rewards[a]
            if termination or truncation:
                break
            else:
                act = model.predict(obs, deterministic=False)[0]

            print(agent, act)
            env.step(act)
    env.close()

    avg_reward = sum(rewards.values()) / len(rewards.values())
    print("Rewards: ", rewards)
    print(f"Avg reward: {avg_reward}")
    return avg_reward

if __name__ == "__main__":
    env_fn = wedding_gossip_environment_v2
    env_kwargs = {}

    learn_steps = 5
    # Train a model (takes ~3 minutes on GPU)
    for i in range(learn_steps):
        train_wedding(env_fn, steps=196_608, seed=0, **env_kwargs)

    # Watch 2 games
    eval(env_fn, num_games=1, render_mode="human", **env_kwargs)
