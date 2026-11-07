// Build helper: export ONE pi-stack component in the assembled case frame.
//   openscad -o parts/<name>.stl -D 'COMPONENT="base"' _pi_part.scad
COMPONENT = "base";
use <../../case/pi-stack-v0.7.scad>;

if      (COMPONENT == "pi")       pi();
else if (COMPONENT == "wittypi")  wittypi();
else if (COMPONENT == "lcd")      lcd();
else if (COMPONENT == "header")   header();
else if (COMPONENT == "leds")     leds();
else if (COMPONENT == "switches") switches();
else if (COMPONENT == "base")     base();
else if (COMPONENT == "mid")      mid();
else if (COMPONENT == "bezel")    bezel();
else if (COMPONENT == "plate")    plate();
