// Query name: MarginalValues
// Requires: ModelParams
//
// What one more unit is worth, in pesos.
//
// The fitted coefficients are expressed in standardised units, which say
// nothing to a reader on their own. Dividing each by its scaler's spread turns
// it back into money per natural unit: per square metre, per bedroom, per
// parking space. This is the same arithmetic the web app's advisor panel
// performs, kept identical on purpose.

let
    Features = ModelParams[numeric_features],
    Coefficients = ModelParams[coef],
    Means = ModelParams[scaler_mean],
    Scales = ModelParams[scaler_scale],
    // The numeric coefficients sit after the one-hot sector block.
    Offset = List.Count(ModelParams[sectors]),
    Rows = List.Transform(
        List.Positions(Features),
        each [
            feature = Features{_},
            coefficient_scaled = Coefficients{Offset + _},
            scaler_mean = Means{_},
            scaler_scale = Scales{_},
            marginal_value_dop = Coefficients{Offset + _} / Scales{_}
        ]
    ),
    Typed = Table.FromRecords(
        Rows,
        type table [
            feature = text,
            coefficient_scaled = number,
            scaler_mean = number,
            scaler_scale = number,
            marginal_value_dop = number
        ]
    )
in
    Typed
