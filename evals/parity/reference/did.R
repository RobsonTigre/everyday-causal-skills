suppressMessages(library(did))
att <- att_gt(yname = "outcome", tname = "time", idname = "unit", gname = "first_treat",
              data = df, control_group = "nevertreated", base_period = "universal",
              bstrap = FALSE)
ov <- aggte(att, type = "simple", na.rm = TRUE)
cat(sprintf("ATT:%f\n", ov$overall.att))
