// Query name: ReferenceCases
// Requires: ModelParams
//
// Three appraisals the training run committed together with the price each
// one must produce. They are the project's parity contract: every client that
// reimplements the model — the serverless API in Python, the TypeScript port,
// and now this report in DAX — has to reproduce them to the cent.
//
// See measures/reference-check.dax for the half that does the checking.

let
    Cases = ModelParams[reference_cases],
    Rows = List.Transform(
        Cases,
        each [
            sector = _[input][sector],
            area_m2 = _[input][area_m2],
            bedrooms = _[input][bedrooms],
            bathrooms = _[input][bathrooms],
            parking_spots = _[input][parking_spots],
            furnished = _[input][furnished],
            age_years = _[input][age_years],
            expected_dop = _[expected]
        ]
    ),
    Typed = Table.FromRecords(
        Rows,
        type table [
            sector = text,
            area_m2 = number,
            bedrooms = Int64.Type,
            bathrooms = Int64.Type,
            parking_spots = Int64.Type,
            furnished = Int64.Type,
            age_years = number,
            expected_dop = number
        ]
    )
in
    Typed
