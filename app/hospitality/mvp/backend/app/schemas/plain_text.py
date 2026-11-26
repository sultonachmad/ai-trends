"""One rule for short free text that ends up in history, registers and printed reports."""

# No markup, control characters, soft hyphen, zero-width or direction marks, line
# separators or word joiners: a reason made of invisible characters is no reason, and
# hidden direction marks can make a register say something else than it seems to.
PLAIN_TEXT = r"^[^<>\x00-\x1f\x7f-\x9f­؜​-‏ -‮⁠-⁩﻿]*$"
