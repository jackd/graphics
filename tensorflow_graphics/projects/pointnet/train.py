# Copyright 2020 The TensorFlow Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Training loop for PointNet v1 on modelnet40."""
import tensorflow as tf
from tensorflow_graphics.datasets import modelnet40
from tensorflow_graphics.nn.layer import pointnet
from tqdm import tqdm
from . import augment  # pylint: disable=g-bad-import-order
from . import helpers  # pylint: disable=g-bad-import-order

from tensorflow_graphics.nn.layer.pointnet import VanillaClassifier
from tensorflow_graphics.projects.pointnet import helpers

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

parser = helpers.ArgumentParser()
parser.add("--batch_size", 32)
parser.add("--num_epochs", 250)
parser.add("--num_points", 2048, help="subsampled (max 2048)")
parser.add("--learning_rate", 1e-3, help="initial Adam learning rate")
parser.add("--lr_decay", True, help="enable learning rate decay")
parser.add("--bn_decay", .5, help="batch norm decay momentum")
parser.add("--tb_every", 100, help="tensorboard frequency (iterations)")
parser.add("--ev_every", 308, help="evaluation frequency (iterations)")
parser.add("--augment_jitter", True, help="use jitter augmentation")
parser.add("--augment_rotate", True, help="use rotate augmentation")
parser.add("--tqdm", True, help="enable the progress bar")
FLAGS = parser.parse_args()

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

optimizer = tf.keras.optimizers.Adam(
    learning_rate=helpers.decayed_learning_rate(FLAGS.learning_rate) if FLAGS.
    lr_decay else FLAGS.learning_rate)

<<<<<<< HEAD
model = VanillaClassifier(num_classes=40, momentum=FLAGS.bn_decay)
=======
model = pointnet.PointNetVanillaClassifier(
    num_classes=40, momentum=FLAGS.bn_decay)
>>>>>>> master

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------


@tf.function
def wrapped_tf_function(points, label):
  """Performs one step of minimization of the loss."""
  # --- training
  with tf.GradientTape() as tape:
    logits = model(points, training=True)
    loss = model.loss(label, logits)
  variables = model.trainable_variables
  gradients = tape.gradient(loss, variables)
  optimizer.apply_gradients(zip(gradients, variables))
  return loss


def train(example):
  """Performs one step of minimization of the loss and populates the summary."""
  points, label = example
  step = optimizer.iterations.numpy()

  # --- optimize
  loss = wrapped_tf_function(points, label)
  if step % FLAGS.tb_every == 0:
    tf.summary.scalar(name="loss", data=loss, step=step)

  # --- report rate in summaries
  if FLAGS.lr_decay and step % FLAGS.tb_every == 0:
    tf.summary.scalar(name="learning_rate",
                      data=optimizer.learning_rate(step),
                      step=step)


# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------


def evaluate():
  """Identify the best accuracy reached during training."""
  step = optimizer.iterations.numpy()
  if "best_accuracy" not in evaluate.__dict__:
    evaluate.best_accuracy = 0
  if step % FLAGS.ev_every != 0:
    return evaluate.best_accuracy
  aggregator = tf.keras.metrics.SparseCategoricalAccuracy()
  for points, labels in ds_test:
    logits = model(points, training=False)
    aggregator.update_state(labels, logits)
  accuracy = aggregator.result()
  evaluate.best_accuracy = max(accuracy, evaluate.best_accuracy)
  tf.summary.scalar(name="accuracy_test", data=accuracy, step=step)
  return evaluate.best_accuracy


# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

<<<<<<< HEAD
ds_train, ds_test = helpers.get_modelnet40_datasets(FLAGS.num_points,
                                                    FLAGS.batch_size,
                                                    FLAGS.augment_jitter,
                                                    FLAGS.augment_rotate,
                                                    FLAGS.num_epochs)
=======
ds_train, info = modelnet40.ModelNet40.load(split="train", with_info=True)
num_examples = info.splits["train"].num_examples
ds_train = ds_train.shuffle(num_examples, reshuffle_each_iteration=True)
ds_train = ds_train.repeat(FLAGS.num_epochs)
ds_train = ds_train.batch(FLAGS.batch_size)
ds_test = modelnet40.ModelNet40.load(split="test").batch(FLAGS.batch_size)
>>>>>>> master

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

try:
  helpers.setup_tensorboard(FLAGS)
  helpers.summary_command(parser, FLAGS)
  total = tf.data.experimental.cardinality(ds_train).numpy()
  pbar = tqdm.tqdm(ds_train, leave=False, total=total, disable=not FLAGS.tqdm)
  for train_example in pbar:
    train(train_example)
    best_accuracy = evaluate()
    pbar.set_postfix_str("best accuracy: {:.3f}".format(best_accuracy))

except KeyboardInterrupt:
  helpers.handle_keyboard_interrupt(FLAGS)
