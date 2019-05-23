import numpy as np
from hac.layer import Layer
import tensorflow as tf
import os
import pickle as cpickle


class Agent:
    """TODO

    TODO

    Attributes
    ----------
    flags : TODO
        TODO
    sess : tf.Session
        the tensorflow session
    subgoal_test_perc : TODO
        subgoal testing ratio each layer will use
    layers : TODO
        TODO
    saver : TODO
        TODO
    model_dir : TODO
        TODO
    model_loc : TODO
        TODO
    goal_array : TODO
        TODO
    current_state : TODO
        TODO
    steps_taken : int
        number of low-level actions executed
    num_updates : int
        number of Q-value updates made after each episode
    performance_log : list of TODO
        used to store performance results
    other_params : TODO
        TODO
    """

    def __init__(self, flags, env, agent_params):
        """Instantiate the Agent object.

        Parameters
        ----------
        flags : TODO
            TODO
        env : TODO
            TODO
        agent_params : TODO
            TODO
        """
        self.flags = flags
        self.sess = tf.Session()

        # Set subgoal testing ratio each layer will use
        self.subgoal_test_perc = agent_params["subgoal_test_perc"]

        # Create agent with number of levels specified by user
        self.layers = [Layer(i, flags, env, self.sess, agent_params)
                       for i in range(flags.layers)]

        # Below attributes will be used help save network parameters
        self.saver = None
        self.model_dir = None
        self.model_loc = None

        # Initialize actor/critic networks.  Load saved parameters if not
        # retraining
        self.initialize_networks()

        # goal_array will store goal for each layer of agent.
        self.goal_array = [None for _ in range(flags.layers)]

        self.current_state = None

        # Track number of low-level actions executed
        self.steps_taken = 0

        # Below hyperparameter specifies number of Q-value updates made after
        # each episode
        self.num_updates = 40

        # Below parameters will be used to store performance results
        self.performance_log = []

        self.other_params = agent_params

    def check_goals(self, env):
        """Determine whether or not each layer's goal was achieved.

        Parameters
        ----------
        env : TODO
            TODO

        Returns
        -------
        TODO
            If applicable, return the highest level whose goal was achieved.
        """
        # goal_status is vector showing status of whether a layer's goal has
        # been achieved
        goal_status = [False for _ in range(self.flags.layers)]

        max_lay_achieved = None

        # Project current state onto the subgoal and end goal spaces
        proj_subgoal = env.project_state_to_subgoal(
            env.sim, self.current_state)
        proj_end_goal = env.project_state_to_end_goal(
            env.sim, self.current_state)

        for i in range(self.flags.layers):

            goal_achieved = True

            # If at highest layer, compare to end goal thresholds
            if i == self.flags.layers - 1:

                # Check dimensions are appropriate
                assert len(proj_end_goal) == len(self.goal_array[i]) == \
                       len(env.end_goal_thresholds), \
                       "Projected end goal, actual end goal, and end goal " \
                       "thresholds should have same dimensions"

                # Check whether layer i's goal was achieved by checking whether
                # projected state is within the goal achievement threshold
                for j in range(len(proj_end_goal)):
                    if np.absolute(self.goal_array[i][j] - proj_end_goal[j]) \
                            > env.end_goal_thresholds[j]:
                        goal_achieved = False
                        break

            # If not highest layer, compare to subgoal thresholds
            else:

                # Check that dimensions are appropriate
                assert len(proj_subgoal) == len(self.goal_array[i]) == \
                       len(env.subgoal_thresholds), \
                       "Projected subgoal, actual subgoal, and subgoal " \
                       "thresholds should have same dimensions"

                # Check whether layer i's goal was achieved by checking whether
                # projected state is within the goal achievement threshold
                for j in range(len(proj_subgoal)):
                    if np.absolute(self.goal_array[i][j] - proj_subgoal[j]) \
                            > env.subgoal_thresholds[j]:
                        goal_achieved = False
                        break

            # If projected state within threshold of goal, mark as achieved
            if goal_achieved:
                goal_status[i] = True
                max_lay_achieved = i
            else:
                goal_status[i] = False

        return goal_status, max_lay_achieved

    def initialize_networks(self):
        """TODO"""
        model_vars = tf.trainable_variables()
        self.saver = tf.train.Saver(model_vars)

        # Set up directory for saving models
        self.model_dir = os.getcwd() + '/models'
        self.model_loc = self.model_dir + '/HAC.ckpt'

        if not os.path.exists(self.model_dir):
            os.makedirs(self.model_dir)

        # Initialize actor/critic networks
        self.sess.run(tf.global_variables_initializer())

        # If not retraining, restore weights
        # if we are not retraining from scratch, just restore weights
        if not self.flags.retrain:
            self.saver.restore(
                self.sess, tf.train.latest_checkpoint(self.model_dir))

    def save_model(self, episode):
        """Save neural network parameters.

        TODO: describe how they are saved

        Parameters
        ----------
        episode : TODO
            TODO
        """
        self.saver.save(self.sess, self.model_loc, global_step=episode)

    def learn(self):
        """Update actor and critic networks for each layer."""
        for i in range(len(self.layers)):
            self.layers[i].learn(self.num_updates)

    def train(self, env, episode_num):
        """Train agent for an episode.

        Parameters
        ----------
        env : TODO
            TODO
        episode_num : int
            TODO

        Returns
        -------
        TODO
            TODO
        """
        # Select final goal from final goal space, defined in
        # "design_agent_and_env.py"
        self.goal_array[self.flags.layers - 1] = env.get_next_goal(
            self.flags.test)
        print("Next End Goal: ", self.goal_array[self.flags.layers - 1])

        # Select initial state from in initial state space, defined in
        # environment.py
        self.current_state = env.reset_sim()
        # print("Initial State: ", self.current_state)

        # Reset step counter
        self.steps_taken = 0

        # Train for an episode
        goal_status, max_lay_achieved = self.layers[self.flags.layers-1].train(
            self, env, episode_num=episode_num)

        # Update actor/critic networks if not testing
        if not self.flags.test:
            self.learn()

        # Return whether end goal was achieved
        return goal_status[self.flags.layers-1]

    # Save performance evaluations
    def log_performance(self, success_rate):
        """Save performance evaluations.

        TODO: describe how this is done and how it's helpful.

        Parameters
        ----------
        success_rate : TODO
            TODO
        """
        # Add latest success_rate to list
        self.performance_log.append(success_rate)

        # Save log
        cpickle.dump(self.performance_log, open("performance_log.p", "wb"))