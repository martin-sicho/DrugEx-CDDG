#!/bin/bash

set -e

echo $line
echo "Test: Generate data for pretraining the fragment-based sequence models..."
echo $line
python -m drugex.dataset \
${DATASET_COMMON_ARGS} \
-i ${TEST_DATA_PRETRAINING} \
-o ${PRETRAINING_PREFIX} \
-mt smiles \
${DATASET_FRAGMENT_ARGS}
echo "Test: Done."

echo $line
echo "Test: Generate data for finetuning the fragment-based sequence models..."
echo $line
python -m drugex.dataset \
${DATASET_COMMON_ARGS} \
-i ${TEST_DATA_FINETUNING} \
-o ${FINETUNING_PREFIX} \
-mt smiles \
${DATASET_FRAGMENT_ARGS}
echo "Test: Done."

echo $line
echo "Test: Generate data for scaffold-based RL of the fragment-based sequence models..."
echo $line
python -m drugex.dataset \
${DATASET_COMMON_ARGS} \
-i ${TEST_DATA_SCAFFOLD} \
-o ${SCAFFOLD_PREFIX} \
-mt smiles \
-s \
${DATASET_FRAGMENT_ARGS}
echo "Test: Done."

echo $line
echo "Test: Pretrain fragment-based sequence transformer model..."
echo $line
python -m drugex.train \
${TRAIN_COMMON_ARGS} \
${TRAIN_VOCAB_ARGS} \
-i "${PRETRAINING_PREFIX}" \
-o "${PRETRAINING_PREFIX}" \
-m PT \
-a trans \
-mt smiles
echo "Test: Done."

echo $line
echo "Test: Fine-tune fragment-based sequence transformer..."
echo $line
python -m drugex.train \
${TRAIN_COMMON_ARGS} \
${TRAIN_VOCAB_ARGS} \
-i "${FINETUNING_PREFIX}" \
-pt "${PRETRAINING_PREFIX}" \
-o "${FINETUNING_PREFIX}" \
-m FT \
-a trans \
-mt smiles
echo "Test: Done."

 echo $line
 echo "Test: RL for the fragment-based sequence transformer..."
 echo $line
 python -m drugex.train \
 ${TRAIN_COMMON_ARGS} \
 ${TRAIN_VOCAB_ARGS} \
 ${TRAIN_RL_ARGS} \
 -i "${FINETUNING_PREFIX}" \
 -ag "${PRETRAINING_PREFIX}_smiles_trans_PT" \
 -pr "${FINETUNING_PREFIX}_smiles_trans_FT" \
 -o "${FINETUNING_PREFIX}_RL" \
 -m RL \
 -a trans \
 -mt smiles
 echo "Test: Done."

echo $line
echo "Test: scaffold-based RL for the fragment-based sequence transformer..."
echo $line
python -m drugex.train \
${TRAIN_COMMON_ARGS} \
${TRAIN_VOCAB_ARGS} \
${TRAIN_RL_ARGS} \
-i "${SCAFFOLD_PREFIX}_smi.txt" \
-ag "${PRETRAINING_PREFIX}_smiles_trans_PT" \
-pr "${FINETUNING_PREFIX}_smiles_trans_FT" \
-o "${SCAFFOLD_PREFIX}_RL" \
-m RL \
-a trans \
-mt smiles
echo "Test: Done."