import gym
import tensorflow as tf
import numpy as np
import random
import math

MAX_EPSILON = 1
MIN_EPSILON = 0.01
LAMBDA = 0.0001
GAMMA = 0.9
TAU = 0.9
BATCH_SIZE = 32

GAME_NAME = 'CartPole-v0'
EPOCH = 20000
EPISODE = 199
EPOCH_PER_TRAINING = 5

RENDER = True

config = tf.ConfigProto(device_count={'GPU': 0})


# class from https://github.com/adventuresinML/adventures-in-ml-code/blob/master/r_learning_tensorflow.py
class Agent:
    def __init__(self, num_states, num_actions, batch_size, gamma=0.9, tau=0.9):
        # Define states, actions and batch size
        self._num_states = num_states
        self._num_actions = num_actions
        self._batch_size = batch_size
        # Define states and actions tensor
        self._states = None
        self._actions = None
        # Define outputs and optimizer
        self._logits = None
        self._optimizer = None
        self._var_init = None
        # Setup the model
        self.gamma = gamma
        self.tau = tau

        self._q_s_a = tf.placeholder(shape=[None, self._num_actions], dtype=tf.float64)
        self.states = tf.placeholder(shape=[None, self._num_states], dtype=tf.float64)
        self.next_state = tf.placeholder(shape=[None, self._num_states], dtype=tf.float64)

        with tf.variable_scope('estimate'):
            self.q_values = self._define_model(self.states)

        with tf.variable_scope('target'):
            self.q_target = self._define_model(self.next_state)

        loss = tf.losses.mean_squared_error(self._q_s_a, self.q_values)
        self._optimizer = tf.train.AdamOptimizer(learning_rate=LAMBDA).minimize(loss)
        self._var_init = tf.global_variables_initializer()

        '''train_params = self.get_variables("estimate")
        fixed_params = self.get_variables("target")

        try:
            self.copy_network_ops = [tf.assign(fixed_v, train_v)
                                     for train_v, fixed_v in zip(train_params, fixed_params)]
        except Exception:
            print("error")'''

        # self.hard_copy_to_target_actor = self.copy_to_target_network(self.q_values, self.q_target)

        self.trainables = tf.trainable_variables()

        self.target_ops = self.update_target_network(self.trainables, self.tau)

    def _define_model(self, input_placeholder):
        # create a couple of fully connected hidden layers
        fc1 = tf.layers.dense(input_placeholder, 16, activation=tf.nn.relu)
        fc2 = tf.layers.dense(fc1, 16, activation=tf.nn.relu)
        logits = tf.layers.dense(fc2, self._num_actions)
        return logits

    def predict_one(self, state, sess):
        return sess.run(self.q_values, feed_dict={self.states: state.reshape(1, self.num_states)})

    def predict_target(self, next_state, sess):
        return sess.run(self.q_target, feed_dict={self.next_state: next_state})

    # Return argument of action
    def predict_action(self, state, sess):
        return np.argmax(self.predict_one(state, sess))

    def predict_batch(self, states, sess):
        return sess.run(self.q_values, feed_dict={self.states: states})

    def train_batch(self, sess, x_batch, y_batch):
        sess.run(self._optimizer, feed_dict={self.states: x_batch, self._q_s_a: y_batch})

    @staticmethod
    def copy_to_target_network(source_network, target_network):
        target_network_update = []
        for v_source, v_target in zip(source_network.variables(), target_network.variables()):
            # this is equivalent to target = source
            update_op = v_target.assign(v_source)
            target_network_update.append(update_op)
        return tf.group(*target_network_update)

    @property
    def num_states(self):
        return self._num_states

    @property
    def num_actions(self):
        return self._num_actions

    @property
    def batch_size(self):
        return self._batch_size

    @property
    def var_init(self):
        return self._var_init

    # def update_target_network(self):
    #    self.session.run(self.hard_copy_to_target_actor)

    def update_target_network(self, trainable_vars, tau):
        total_vars = len(trainable_vars)
        op_holder = []
        for idx, var in enumerate(trainable_vars[0: total_vars // 2]):
            target_layer_id = idx + total_vars // 2
            op_holder.append(
                trainable_vars[target_layer_id].assign(
                    (var.value() * tau) + ((1 - tau) * trainable_vars[target_layer_id].value())))
        return op_holder

    def update_target(self, sess):
        for op in self.target_ops:
            sess.run(op)


# class from https://github.com/adventuresinML/adventures-in-ml-code/blob/master/r_learning_tensorflow.py
class Memory:
    def __init__(self, max_memory):
        self._max_memory = max_memory
        self._samples = []

    def add_sample(self, sample):
        self._samples.append(sample)
        if len(self._samples) > self._max_memory:
            self._samples.pop(0)

    def sample(self, no_samples):
        if no_samples > len(self._samples):
            return random.sample(self._samples, len(self._samples))
        else:
            return random.sample(self._samples, no_samples)


def choose_action(sess, agent, state):
    global eps, MIN_EPSILON, MAX_EPSILON
    if random.random() < eps:
        act = random.randint(0, agent.num_actions - 1)
    else:
        act = np.argmax(agent.predict_one(state, sess))
    if eps > MIN_EPSILON:
        eps = eps - (MAX_EPSILON - MIN_EPSILON) / 1000.0
    return act


def normalise_state(state):
    # global max_state
    state[0] = state[0] / 1.6  # max_state[0]
    state[1] = state[1] / 1.5  # max_state[1]
    state[2] = state[2] / 12  # max_state[2]
    state[3] = state[3] / 0.6  # max_state[3]
    return state
    '''new_state = np.zeros((1, num_states))[0]
    new_state[0] = state[2]
    new_state[1] = state[3]
    return new_state'''


def replay(sess, agent, memory):
    batch = memory.sample(agent.batch_size)
    states = np.array([val[0] for val in batch])
    next_states = np.array([(np.zeros(agent.num_states)
                             if val[3] is None else val[3]) for val in batch])
    # predict Q(s,a) given the batch of states
    q_s_a = agent.predict_batch(states, sess)
    # predict Q(s',a') - so that we can do gamma * max(Q(s'a')) below
    q_s_a_d = agent.predict_target(next_states, sess)
    # setup training arrays
    x = np.zeros((len(batch), agent.num_states))
    y = np.zeros((len(batch), agent.num_actions))
    for i, b in enumerate(batch):
        state, action, reward, next_state = b[0], b[1], b[2], b[3]
        # get the current q values for all actions in state
        current_q = q_s_a[i]
        # update the q value for action
        if next_state is None:
            # in this case, the game completed after action, so there is no max Q(s',a')
            # prediction possible
            current_q[action] = reward
        else:
            current_q[action] = reward + GAMMA * np.amax(q_s_a_d[i])
        x[i] = state
        y[i] = current_q
    agent.train_batch(sess, x, y)


env = gym.make(GAME_NAME)

num_states = env.env.observation_space.shape[0]
max_state = env.env.observation_space.high
num_actions = env.env.action_space.n

agent = Agent(num_states, num_actions, BATCH_SIZE, gamma=GAMMA, tau=TAU)
mem = Memory(50000)

eps = MAX_EPSILON
with tf.Session(config=config) as sess:
    sess.run(agent.var_init)
    for epoch in range(EPOCH):
        _state = env.reset()
        state = normalise_state(_state)
        tot_reward = 0
        cum_reward = 0
        for episode in range(EPISODE):
            if RENDER:
                env.render()
            action = choose_action(sess, agent, state)
            _next_state, reward, done, info = env.step(action)
            next_state = normalise_state(_next_state)
            cum_reward = reward / 10.0
            if done:
                cum_reward = -0.1
                # next_state = None
            tot_reward += cum_reward
            mem.add_sample((state, action, cum_reward, next_state))

            # Train our network
            if (episode + 1) % EPOCH_PER_TRAINING == 0:
                replay(sess, agent, mem)

            state = next_state

            # if done:
            # break

        # print("{}: sum reward: {}".format(epoch + 1, tot_reward))
        agent.update_target(sess)
        print("{}: sum reward: {}, episodes: {}".format(epoch + 1, tot_reward, episode))
