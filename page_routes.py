"""Adobe page id -> local site route, so links between archived pages stay inside the site.

When the extractor meets a link or button pointing at an Adobe Express page listed here (for example
the hub page's buttons to each subject page), it rewrites the target to the local route and marks it
as an internal link. Links to pages not listed here are kept as external Adobe links.

The page id is the segment after /page/ or /webpage/ in the Adobe URL
(https://express.adobe.com/page/<ID>/  or  https://new.express.adobe.com/webpage/<ID>).
Add every page you archive so its siblings link to it.
"""

PAGE_ROUTES = {
    # NO EXCUSES! DIY Actor Demo Reel Clips
    "srf8IpDO7ZkIU": "/learn/ne-9vphb2b1vsvl93/welcome",
    "MltFArqt4mOOT": "/learn/ne-9vphb2b1vsvl93/write-it",
    "6DKzqO1Wiw758": "/learn/ne-9vphb2b1vsvl93/plan-prep-it",
    "f5hjv4sMwNeA3": "/learn/ne-9vphb2b1vsvl93/shoot-it",
    "GMt6OK0rvfYVm": "/learn/ne-9vphb2b1vsvl93/edit-it",
    "z4dBmikw9rtLK": "/learn/ne-9vphb2b1vsvl93/use-it",
    # The Perfect Self Tape
    "4N3CH5BgyUPgp": "/learn/pst-mz3vspur4szgo4",
    "t89Ol45aZnWWO": "/learn/pst-mz3vspur4szgo4/equipment-guide",
    "fKEcYmY4tk1Ru": "/learn/pst-mz3vspur4szgo4/properly-lit",
    "5HkJaHOKEnWA5": "/learn/pst-mz3vspur4szgo4/perfect-frame",
    "HTdXKtkSq3Ksq": "/learn/pst-mz3vspur4szgo4/slates-that-shine",
    "9h9pR9OX1OZq7": "/learn/pst-mz3vspur4szgo4/role-of-the-reader",
    "FrbVFiuNM7Jxy": "/learn/pst-mz3vspur4szgo4/performance-coaching",
    "OQdMObzEI8etD": "/learn/pst-mz3vspur4szgo4/quick-editing",
    "ZYQXknWCAzt3i": "/learn/pst-mz3vspur4szgo4/parent-survival-tips",
    "E3kmokZywrFef": "/learn/pst-mz3vspur4szgo4/sending-tapes",
    "ko5JZe1bqtBnz": "/learn/pst-mz3vspur4szgo4/bending-the-rules",
}
