from diff_diff import CallawaySantAnna

res = CallawaySantAnna(control_group="never_treated", base_period="universal").fit(
    df, outcome="outcome", unit="unit", time="time",
    first_treat="first_treat", aggregate="all")
print(f"ATT:{res.overall_att}")
