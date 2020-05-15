# Copyright 2020 Google LLC
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
# pylint: disable=missing-function-docstring
import functools
import tensorflow as tf

from tqdm import tqdm
from tensorflow_graphics.datasets.modelnet40 import ModelNet40
from tensorflow_graphics.nn.layer.pointnet import PointNetVanillaClassifier as PointNet
from tensorflow_graphics.projects.pointnet import augment
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
parser.add("--tfds", True, help="use TFDS dataset loader")
parser.add("--augment_rotation", True, help="use rotation augmentations")
parser.add("--augment_jitter", True, help="use jitter augmentations")
parser.add("--tqdm", True, help="enable the progress bar")
parser.add_argument("--dryrun", action="store_true")
FLAGS = parser.parse_args()

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

if FLAGS.lr_decay:
  lr_scheduler = tf.keras.optimizers.schedules.ExponentialDecay(
      FLAGS.learning_rate,
      decay_steps=6250,  #< 200.000 / 32 (batch size) (from original pointnet)
      decay_rate=0.7,
      staircase=True)
  optimizer = tf.keras.optimizers.Adam(learning_rate=lr_scheduler)
else:
  optimizer = tf.keras.optimizers.Adam(learning_rate=FLAGS.learning_rate)

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

model = PointNet(num_classes=40, momentum=FLAGS.bn_decay)

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
  points = example["points"]
  label = example["label"]
  step = optimizer.iterations.numpy()

  # --- optimize
  loss = wrapped_tf_function(points, label)
  if step % FLAGS.tb_every == 0:
    tf.summary.scalar(name="loss", data=loss, step=step)

  # --- report rate in summaries
  if FLAGS.lr_decay and step % FLAGS.tb_every == 0:
    tf.summary.scalar(name="learning_rate", data=lr_scheduler(step), step=step)


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
  for example in ds_test:
    points, labels = example["points"], example["label"]
    logits = model(points, training=False)
    aggregator.update_state(labels, logits)
  accuracy = aggregator.result()
  evaluate.best_accuracy = max(accuracy, evaluate.best_accuracy)
  tf.summary.scalar(name="accuracy_test", data=accuracy, step=step)
  return evaluate.best_accuracy


# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------


def preprocess(example, augment_rotation=False, augment_jitter=False):
  points = example["points"][:FLAGS.num_points]
  if augment_rotation:
    points = augment.rotate(points)
  if augment_jitter:
    points = augment.jitter(points)
  example["points"] = points
  return example


if not FLAGS.dryrun:
  ds_train, info = ModelNet40.load(split="train", with_info=True)
  num_examples = info.splits["train"].num_examples
  ds_train = ds_train.shuffle(num_examples, reshuffle_each_iteration=True)
  ds_train = ds_train.repeat(FLAGS.num_epochs)
  ds_train = ds_train.map(
      functools.partial(preprocess,
                        augment_jitter=FLAGS.augment_jitter,
                        augment_rotation=FLAGS.augment_rotation),
      tf.data.experimental.AUTOTUNE)
  ds_train = ds_train.batch(FLAGS.batch_size).prefetch(
      tf.data.experimental.AUTOTUNE)
  ds_test = ModelNet40.load(split="test")
  ds_test = ds_test.map(preprocess, tf.data.experimental.AUTOTUNE)
  ds_test = ds_test.batch(FLAGS.batch_size).prefetch(
      tf.data.experimental.AUTOTUNE)

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

if not FLAGS.dryrun:
  try:
    helpers.setup_tensorboard(FLAGS)
    helpers.summary_command(parser, FLAGS)
    total = tf.data.experimental.cardinality(ds_train).numpy()
    pbar = tqdm(ds_train, leave=False, total=total, disable=not FLAGS.tqdm)
    for train_example in pbar:
      train(train_example)
      best_accuracy = evaluate()
      pbar.set_postfix_str("best accuracy: {:.3f}".format(best_accuracy))

  except KeyboardInterrupt:
    helpers.handle_keyboard_interrupt(FLAGS)
