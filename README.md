# yashaswiupmon.github.io

This repository contains a JSON-driven resume website and its source resume PDF.
The single-page design is inspired by the React Resume Template demo while
remaining a static site, so it can be published directly with GitHub Pages.

## Publishing

The `Build and deploy resume site` workflow generates `resume.json` from
`resume.pdf`, saves any changes back to the repository, builds the static site
artifact, and deploys it to GitHub Pages. The deployment job waits for the
build job to finish. The workflow runs on pushes to the default branch and can
also be started manually from the Actions tab. In the repository's
**Settings → Pages**, set the build and deployment source to **GitHub Actions**.

The page supports light and dark themes. Visitors can switch using the button
in the navigation bar; their choice is saved in their browser.

The homepage has About, Resume, Portfolio, and Contact sections. Research
publications and projects are shown as image-backed portfolio cards. Card
details are available on hover or keyboard focus, and the details remain
visible on touch devices. Publication image metadata is retained when the
resume PDF is parsed.

## Adding a custom resume section

Work experience entries are rendered from `work` in `resume.json`; the PDF
parser recognizes additional roles when they use the existing date, title, and
bullet format.

For a new PDF section, first add its exact heading and the display title to
`customSectionHeadings` in `resume.json`. For example:

```json
"customSectionHeadings": {
  "Volunteer Experience": "Volunteer Experience"
}
```

Use bullet points under that heading in the PDF. On the next build, the parser
will extract those items into `customSections`, and the page will add the
section and a navigation link. Arbitrary new PDF headings are not inferred
automatically; they need to be listed in `customSectionHeadings`.