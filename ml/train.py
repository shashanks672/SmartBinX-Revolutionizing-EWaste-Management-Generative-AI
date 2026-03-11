"""
ml/train.py
Simple transfer learning training script using MobileNetV2.
Saves model to ../models/classifier_model.h5

Usage:
  - Prepare dataset in data/train/<class_name> images...
  - Optional validation folder data/val/<class_name> ...
  - python3 ml/train.py
"""

import os
import tensorflow as tf
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.layers import Dense, GlobalAveragePooling2D, Dropout
from tensorflow.keras import Model
from tensorflow.keras.preprocessing.image import ImageDataGenerator

# CONFIG - change these as needed
DATA_DIR = "data"
TRAIN_DIR = os.path.join(DATA_DIR, "train")
VAL_DIR = os.path.join(DATA_DIR, "val")  # optional; if not present will use validation_split
OUT_MODEL = "models/classifier_model.h5"
IMG_SIZE = (224, 224)
BATCH_SIZE = 16
EPOCHS = 5
AUTOTUNE = tf.data.AUTOTUNE

def build_model(num_classes):
    base = MobileNetV2(include_top=False, input_shape=IMG_SIZE + (3,), weights='imagenet')
    x = GlobalAveragePooling2D()(base.output)
    x = Dropout(0.3)(x)
    out = Dense(num_classes, activation='softmax')(x)
    model = Model(inputs=base.input, outputs=out)
    # freeze base
    for layer in base.layers:
        layer.trainable = False
    model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])
    return model

def main():
    if not os.path.exists(TRAIN_DIR):
        print("Training directory not found:", TRAIN_DIR)
        print("Create folders like data/train/e-waste, data/train/plastic, etc. with images inside.")
        return

    # If explicit validation directory exists, use separate generator, otherwise use validation_split
    if os.path.exists(VAL_DIR) and any(os.scandir(VAL_DIR)):
        print("Using explicit validation dir:", VAL_DIR)
        train_datagen = ImageDataGenerator(rescale=1./255)
        val_datagen = ImageDataGenerator(rescale=1./255)
        train_gen = train_datagen.flow_from_directory(TRAIN_DIR, target_size=IMG_SIZE, batch_size=BATCH_SIZE)
        val_gen = val_datagen.flow_from_directory(VAL_DIR, target_size=IMG_SIZE, batch_size=BATCH_SIZE)
    else:
        print("Using validation_split with training dir")
        datagen = ImageDataGenerator(rescale=1./255, validation_split=0.2,
                                     rotation_range=20, width_shift_range=0.1, height_shift_range=0.1,
                                     shear_range=0.1, zoom_range=0.1, horizontal_flip=True)
        train_gen = datagen.flow_from_directory(TRAIN_DIR, target_size=IMG_SIZE, batch_size=BATCH_SIZE, subset='training')
        val_gen = datagen.flow_from_directory(TRAIN_DIR, target_size=IMG_SIZE, batch_size=BATCH_SIZE, subset='validation')

    num_classes = train_gen.num_classes
    print("Found classes:", train_gen.class_indices)

    model = build_model(num_classes)
    print(model.summary())

    # Train
    model.fit(train_gen, validation_data=val_gen, epochs=EPOCHS)

    # Save
    os.makedirs(os.path.dirname(OUT_MODEL), exist_ok=True)
    model.save(OUT_MODEL)
    print("Saved model to", OUT_MODEL)

if __name__ == "__main__":
    main()
