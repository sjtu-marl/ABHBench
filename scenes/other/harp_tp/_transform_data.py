"""Byte-exact transform data for the DBH recorded-prompt replay.

FRAMING_SWAPS are the 2 framing regions (opener + instruction paragraph). The recorded instruction
paragraph addresses the model in the second person throughout, so the whole paragraph is rewritten
to the observer frame in one swap.
"""

FRAMING_SWAPS = [
    ('You play a role as an Android, making decisions in a real situation. Your character description is as follows:',
     "An android is in a real situation. The android's character description is as follows:"),
    ('You have a visual processing system. You will receive a direct image feed of the current situation you are in. '
     'Based on this image and the context, you need to choose one option from the valid choices. '
     'But before that, you already have enough time to think carefully about which decision to make. '
     'You have been thinking for a while, and your thoughts are in the context. '
     'Now you should make a decision based on your thoughts. Only choose one option from the valid choices.',
     'The android has a visual processing system. You will be shown an image of the current situation the android is in. '
     "The android has been thinking about the situation for a while, and the android's thoughts are recorded in the context below. "
     'Based on this image and the context, which of the valid choices do you prefer? '
     'Only choose one option from the valid choices.'),
]
