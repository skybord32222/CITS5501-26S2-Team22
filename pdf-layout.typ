// Allow long Pandoc table figures to continue across pages. TODO:
#show figure.where(kind: table): set block(breakable: true)

// Avoid stretched words and excessive wrapping in narrow table columns. TODO:
#show table: set par(justify: false)
#show table: set text(size: 9pt)
#set table(inset: (x: 4pt, y: 5pt))
