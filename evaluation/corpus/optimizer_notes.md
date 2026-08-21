# Optimizer Notes

Synthetic primer used in an internal ML reading group.

## Gradient descent

Gradient descent updates parameters in the opposite direction of the loss gradient.
A constant step size is a development default, not an optimal schedule.

## Adam

Adam maintains exponential moving averages of both the gradient and the squared gradient.
Those averages are bias-corrected before the parameter update.
