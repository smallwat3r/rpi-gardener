// RPi Gardener Display Plate
// Top plate for mounting OLED screens and LCD 1602A above the HAT
// Export to STL: OpenSCAD -> File -> Export -> STL

/* [Base Dimensions] */
// Extended depth to accommodate LCD 1602A below OLEDs
base_width = 90;          // mm
base_depth = 105;         // mm - extended from 62mm to fit 1602A
base_thickness = 3;       // mm
corner_radius = 3;        // mm

/* [Mounting Holes - RPi/HAT Pattern] */
// Standard RPi 4 mounting pattern: 58mm x 49mm
// Positioned toward the top of the extended plate
hole_spacing_x = 58;      // mm between holes horizontally
hole_spacing_y = 49;      // mm between holes vertically
hole_diameter = 3.2;      // mm - M3 clearance hole
hole_offset_x = (90 - 58) / 2;   // 16mm - centered on base width
hole_offset_y = base_depth - 62 + (62 - 49) / 2;  // Offset to top portion

/* [OLED Display Configuration] */
// Number of OLED displays: 1 = single centered, 2 = dual side by side
oled_count = 2;

// OLED type: 0 = Custom, 1 = 0.96" OLED (SSD1306), 2 = 1.3" OLED
oled_type = 1;

// Gap between OLED displays when using dual mode (mm)
oled_gap = 6;

// OLED vertical position from top edge (mm)
oled_offset_from_top = 20;

/* [LCD 1602A Configuration] */
// Enable LCD 1602A mounting
lcd_1602_enabled = true;

// LCD 1602A dimensions (standard module ~80x36mm, display ~64.5x16mm)
lcd_1602_cutout = [66, 18];           // Display window
lcd_1602_mount_spacing = [75, 31];    // Mounting hole spacing
lcd_1602_module_size = [80, 36];      // Full module size

// LCD vertical position from bottom edge (mm)
lcd_offset_from_bottom = 8;

/* [Custom OLED Cutout] */
// Only used when oled_type = 0
custom_cutout_width = 30;   // mm
custom_cutout_height = 15;  // mm

/* [Display Module Mounting] */
display_mount_holes = true;
oled_mount_hole_diameter = 2.5;   // mm - M2.5 clearance for OLEDs
lcd_mount_hole_diameter = 3.2;    // mm - M3 clearance for 1602A

// OLED presets
oled_096_cutout = [24, 13];
oled_096_mount_spacing = [23.5, 23.5];
oled_096_module_size = [27, 27];

oled_13_cutout = [32, 18];
oled_13_mount_spacing = [29, 27];
oled_13_module_size = [35, 33];

// Get OLED dimensions based on type
function get_oled_cutout() =
    oled_type == 1 ? oled_096_cutout :
    oled_type == 2 ? oled_13_cutout :
    [custom_cutout_width, custom_cutout_height];

function get_oled_mount_spacing() =
    oled_type == 1 ? oled_096_mount_spacing :
    oled_type == 2 ? oled_13_mount_spacing :
    [custom_cutout_width + 6, custom_cutout_height + 6];

function get_oled_module_size() =
    oled_type == 1 ? oled_096_module_size :
    oled_type == 2 ? oled_13_module_size :
    [custom_cutout_width + 6, custom_cutout_height + 6];

// Modules
module rounded_rect(w, d, h, r) {
    hull() {
        translate([r, r, 0]) cylinder(h=h, r=r, $fn=32);
        translate([w-r, r, 0]) cylinder(h=h, r=r, $fn=32);
        translate([r, d-r, 0]) cylinder(h=h, r=r, $fn=32);
        translate([w-r, d-r, 0]) cylinder(h=h, r=r, $fn=32);
    }
}

module rounded_cutout(w, h, thickness, r=2) {
    hull() {
        translate([r, r, 0]) cylinder(h=thickness, r=r, $fn=16);
        translate([w-r, r, 0]) cylinder(h=thickness, r=r, $fn=16);
        translate([r, h-r, 0]) cylinder(h=thickness, r=r, $fn=16);
        translate([w-r, h-r, 0]) cylinder(h=thickness, r=r, $fn=16);
    }
}

// OLED display cutout and mounting holes
module oled_cutout_and_mount(center_x, center_y, cutout, mount_spacing) {
    // Display cutout
    translate([center_x - cutout[0]/2, center_y - cutout[1]/2, -0.1])
        rounded_cutout(cutout[0], cutout[1], base_thickness + 0.2);

    // Mounting holes (M2.5)
    if (display_mount_holes) {
        for (dx = [-1, 1]) {
            for (dy = [-1, 1]) {
                translate([
                    center_x + dx * mount_spacing[0] / 2,
                    center_y + dy * mount_spacing[1] / 2,
                    -0.1
                ])
                cylinder(h=base_thickness+0.2, d=oled_mount_hole_diameter, $fn=32);
            }
        }
    }
}

// LCD 1602A cutout and mounting holes
module lcd_1602_cutout_and_mount(center_x, center_y) {
    // Display window cutout
    translate([center_x - lcd_1602_cutout[0]/2, center_y - lcd_1602_cutout[1]/2, -0.1])
        rounded_cutout(lcd_1602_cutout[0], lcd_1602_cutout[1], base_thickness + 0.2, r=1);

    // Mounting holes (M3) at corners
    if (display_mount_holes) {
        for (dx = [-1, 1]) {
            for (dy = [-1, 1]) {
                translate([
                    center_x + dx * lcd_1602_mount_spacing[0] / 2,
                    center_y + dy * lcd_1602_mount_spacing[1] / 2,
                    -0.1
                ])
                cylinder(h=base_thickness+0.2, d=lcd_mount_hole_diameter, $fn=32);
            }
        }
    }
}

// Main assembly
module display_plate() {
    oled_cutout = get_oled_cutout();
    oled_mount_spacing = get_oled_mount_spacing();
    oled_module_size = get_oled_module_size();

    // Center X of plate
    center_x = base_width / 2;

    // OLED Y position (from top)
    oled_center_y = base_depth - oled_offset_from_top - oled_module_size[1] / 2;

    // LCD Y position (from bottom)
    lcd_center_y = lcd_offset_from_bottom + lcd_1602_module_size[1] / 2;

    // Calculate OLED positions for dual mode
    oled_dual_offset = (oled_module_size[0] + oled_gap) / 2;

    difference() {
        // Base plate
        rounded_rect(base_width, base_depth, base_thickness, corner_radius);

        // RPi/HAT mounting holes (M3)
        translate([hole_offset_x, hole_offset_y, -0.1])
            cylinder(h=base_thickness+0.2, d=hole_diameter, $fn=32);
        translate([hole_offset_x + hole_spacing_x, hole_offset_y, -0.1])
            cylinder(h=base_thickness+0.2, d=hole_diameter, $fn=32);
        translate([hole_offset_x, hole_offset_y + hole_spacing_y, -0.1])
            cylinder(h=base_thickness+0.2, d=hole_diameter, $fn=32);
        translate([hole_offset_x + hole_spacing_x, hole_offset_y + hole_spacing_y, -0.1])
            cylinder(h=base_thickness+0.2, d=hole_diameter, $fn=32);

        // OLED cutouts and mounting holes
        if (oled_count == 1) {
            oled_cutout_and_mount(center_x, oled_center_y, oled_cutout, oled_mount_spacing);
        } else {
            oled_cutout_and_mount(center_x - oled_dual_offset, oled_center_y, oled_cutout, oled_mount_spacing);
            oled_cutout_and_mount(center_x + oled_dual_offset, oled_center_y, oled_cutout, oled_mount_spacing);
        }

        // LCD 1602A cutout and mounting holes
        if (lcd_1602_enabled) {
            lcd_1602_cutout_and_mount(center_x, lcd_center_y);
        }
    }
}

// Render the plate
display_plate();

// Info
oled_cutout = get_oled_cutout();
oled_module_size = get_oled_module_size();
oled_names = ["Custom", "0.96\" OLED (SSD1306)", "1.3\" OLED"];

echo("=== RPi Gardener Display Plate ===");
echo(str("Base size: ", base_width, "mm x ", base_depth, "mm x ", base_thickness, "mm"));
echo("");
echo("OLED Section (top):");
echo(str("  Count: ", oled_count));
echo(str("  Type: ", oled_names[oled_type]));
echo(str("  Cutout: ", oled_cutout[0], "mm x ", oled_cutout[1], "mm"));
if (oled_count == 2) {
    echo(str("  Gap: ", oled_gap, "mm"));
    echo(str("  Total width: ", oled_module_size[0] * 2 + oled_gap, "mm"));
}
echo("");
if (lcd_1602_enabled) {
    echo("LCD 1602A Section (bottom):");
    echo(str("  Cutout: ", lcd_1602_cutout[0], "mm x ", lcd_1602_cutout[1], "mm"));
    echo(str("  Mount spacing: ", lcd_1602_mount_spacing[0], "mm x ", lcd_1602_mount_spacing[1], "mm"));
}
echo("");
echo("Assembly:");
echo("1. Stack on top of HAT using M3 screws and spacers");
echo("2. Mount OLED module(s) using M2.5 screws");
echo("3. Mount LCD 1602A using M3 screws");
echo("4. Route wires through cutouts to HAT");
