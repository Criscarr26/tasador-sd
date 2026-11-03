// Query name: Sectors
// Requires: ModelParams
//
// One row per sector the model knows. The first N entries of `coef` are the
// one-hot offsets for the sectors, in the same order as the `sectors` list;
// the numeric coefficients follow them.
//
// `average_rent_dop` is the mean rent of that sector in the training data,
// and it is what makes the coefficient readable: the offset says how much of
// that average the address itself explains, once size and condition are held
// constant.

let
    Sectors = ModelParams[sectors],
    Coefficients = ModelParams[coef],
    Averages = ModelParams[avg_price_by_sector],
    Rows = List.Transform(
        List.Positions(Sectors),
        each [
            sector = Sectors{_},
            sector_coefficient = Coefficients{_},
            average_rent_dop = Record.FieldOrDefault(Averages, Sectors{_}, null)
        ]
    ),
    Typed = Table.FromRecords(
        Rows,
        type table [
            sector = text,
            sector_coefficient = number,
            average_rent_dop = number
        ]
    )
in
    Typed
