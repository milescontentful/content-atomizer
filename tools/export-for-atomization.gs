/**
 * export-for-atomization.gs  —  self-contained, paste into any deck's Apps Script editor
 *
 * HOW TO USE
 * ----------
 *   1. Open the target Google Slides presentation.
 *   2. Extensions → Apps Script (opens a script bound to this presentation).
 *   3. Click "+ New file" → Script, name it "export-for-atomization".
 *   4. Delete the default myFunction() stub and paste this entire file.
 *   5. Select exportForAtomization in the function selector and click ▶ Run.
 *   6. Approve the permissions prompt (Drive + Slides access for this script).
 *   7. Click the link in the dialog, then File → Download.
 *   8. Rename the file to a short deck ID, e.g. "personalization-q2fy27.json"
 *      and drop it in: content-atomization-poc/pipeline/staging/01_raw/
 *
 * THEN IN THE ATOMIZATION REPO
 * -----------------------------
 *   npm run extract -- --deck personalization-q2fy27
 *   python pipeline/run.py --deck-id personalization-q2fy27 --dry-run
 *   python pipeline/run.py --deck-id personalization-q2fy27 --apply
 */

// ─── Entry point ──────────────────────────────────────────────────────────────

function exportForAtomization() {
  var presentation = SlidesApp.getActivePresentation();
  if (!presentation) {
    Logger.log('No active presentation found.');
    return;
  }

  var presentationId = presentation.getId();
  var title = presentation.getName();
  var slides = presentation.getSlides();
  var normalizedSlides = [];

  for (var i = 0; i < slides.length; i++) {
    var slide = slides[i];
    var slideIndex = i + 1;

    var slideTitle = _getSlideTitle(slide);
    if (!slideTitle) slideTitle = 'Slide ' + slideIndex;

    var bodyLines = _getBodyLines(slide, slideTitle);
    var bodyText = _bodyLinesToText(bodyLines);
    var slideType = _getSlideType(slide, bodyText);
    var notes = _getSpeakerNotes(slide);
    var subtitle = _getSlideSubtitle(slide);

    var elements = slide.getPageElements();
    var imageCount = 0;
    for (var j = 0; j < elements.length; j++) {
      if (elements[j].getPageElementType() === SlidesApp.PageElementType.IMAGE) {
        imageCount++;
      }
    }

    var slideData = {
      slideIndex: slideIndex,
      objectId: slide.getObjectId(),
      layoutName: _getLayoutName(slide),
      slideType: slideType,
      title: slideTitle,
      bodyText: bodyText,
      bodyLines: bodyLines,
      speakerNotes: notes,
      imageCount: imageCount
    };

    if (subtitle) slideData.subtitle = subtitle;

    normalizedSlides.push(slideData);
  }

  var payload = {
    presentationId: presentationId,
    title: title,
    slides: normalizedSlides
  };

  var json = JSON.stringify(payload, null, 2);
  var safeTitle = title.replace(/[^a-zA-Z0-9\s\-]/g, '').replace(/\s+/g, '-').toLowerCase();
  var fileName = safeTitle + '-atomization-export.json';
  var file = DriveApp.createFile(fileName, json, MimeType.PLAIN_TEXT);

  Logger.log('Export complete — ' + slides.length + ' slides');
  Logger.log('File: ' + file.getUrl());

  var html = HtmlService.createHtmlOutput(
    '<style>body{font-family:sans-serif;padding:14px;font-size:13px;line-height:1.5}</style>' +
    '<p><strong>' + slides.length + ' slides</strong> exported from<br><em>' + title + '</em></p>' +
    '<p>Saved to Google Drive:<br>' +
    '<a href="' + file.getUrl() + '" target="_blank" style="word-break:break-all">' + fileName + '</a></p>' +
    '<hr style="border:none;border-top:1px solid #ddd;margin:10px 0">' +
    '<p style="color:#555;font-size:12px">Download the file and save it to:<br>' +
    '<code>pipeline/staging/01_raw/&lt;deck-id&gt;.json</code><br><br>' +
    'Then run:<br>' +
    '<code>npm run extract -- --deck &lt;deck-id&gt;</code></p>'
  ).setWidth(460).setHeight(230);

  SlidesApp.getUi().showModalDialog(html, 'Atomization Export Complete');
}

// ─── Helpers (mapper functions, self-contained) ───────────────────────────────

var _LAYOUT_TO_SLIDE_TYPE = {
  'TITLE':                          'title-slide',
  'SECTION_HEADER':                 'section-break',
  'SECTION_TITLE_AND_DESCRIPTION':  'section-break',
  'BIG_NUMBER':                     'statistics',
  'MAIN_POINT':                     'statistics',
  'TITLE_AND_BODY':                 'body',
  'ONE_COLUMN_TEXT':                'body',
  'TITLE_ONLY':                     'body',
  'BLANK':                          'body',
  'CAPTION_ONLY':                   'body',
  'CUSTOM':                         'body',
  'TITLE_AND_TWO_COLUMNS':          'body'
};

var _NOISE_PATTERNS = [
  /^©\s*\d{4}\s+Contentful\s*$/i,
  /^©\s*\d{4}\s*$/
];

var _BULLET_CHARS = ['●', '•', '·', '◦', '▪', '▸', '➢', '-'];

function _isBulletLine(line) {
  for (var i = 0; i < _BULLET_CHARS.length; i++) {
    if (line.indexOf(_BULLET_CHARS[i]) === 0) return true;
  }
  return false;
}

function _stripBullet(line) {
  return line.replace(/^[●•·◦▪▸➢\-]\s*/, '').trim();
}

function _isNoiseLine(line) {
  for (var i = 0; i < _NOISE_PATTERNS.length; i++) {
    if (_NOISE_PATTERNS[i].test(line)) return true;
  }
  return false;
}

function _cleanText(text) {
  return text.split('\n').map(function(l) { return l.trim(); })
    .filter(function(l) { return l && !_isNoiseLine(l); }).join('\n');
}

function _isStatHeavy(bodyText) {
  var lines = bodyText.split('\n');
  var n = 0;
  for (var i = 0; i < lines.length; i++) {
    if (/\d+%/.test(lines[i]) || /^\d+x\b/i.test(lines[i]) ||
        /\b\d+\s*(hour|day|week|minute)/i.test(lines[i])) n++;
  }
  return n >= 2;
}

function _getLayoutName(slide) {
  try { return slide.getLayout().getLayoutName(); } catch (e) { return 'CUSTOM'; }
}

function _getSlideType(slide, bodyText) {
  var layoutType = 'body';
  try {
    layoutType = _LAYOUT_TO_SLIDE_TYPE[slide.getLayout().getLayoutName()] || 'body';
  } catch (e) {}
  if (layoutType === 'body' && bodyText && _isStatHeavy(bodyText)) return 'statistics';
  return layoutType;
}

function _getSlideTitle(slide) {
  var elements = slide.getPageElements();
  for (var i = 0; i < elements.length; i++) {
    var el = elements[i];
    if (el.getPageElementType() !== SlidesApp.PageElementType.SHAPE) continue;
    var shape = el.asShape();
    var pt = shape.getPlaceholderType();
    if (pt === SlidesApp.PlaceholderType.TITLE || pt === SlidesApp.PlaceholderType.CENTERED_TITLE) {
      var text = _cleanText(shape.getText().asString().trim());
      if (text) return text;
    }
  }
  var candidates = [];
  for (var i = 0; i < elements.length; i++) {
    var el = elements[i];
    if (el.getPageElementType() !== SlidesApp.PageElementType.SHAPE) continue;
    var shape = el.asShape();
    var pt = shape.getPlaceholderType();
    if (pt === SlidesApp.PlaceholderType.SUBTITLE || pt === SlidesApp.PlaceholderType.BODY) continue;
    var raw = _cleanText(shape.getText().asString().trim());
    if (!raw) continue;
    var lines = raw.split('\n').filter(function(l) { return l.trim(); });
    var first = lines[0] || '';
    if (first.length > 120 || _isBulletLine(first)) continue;
    candidates.push({ text: first, top: el.getTop() });
  }
  if (candidates.length === 0) return '';
  candidates.sort(function(a, b) { return a.top - b.top; });
  return candidates[0].text;
}

function _getSlideSubtitle(slide) {
  var elements = slide.getPageElements();
  for (var i = 0; i < elements.length; i++) {
    var el = elements[i];
    if (el.getPageElementType() !== SlidesApp.PageElementType.SHAPE) continue;
    var shape = el.asShape();
    if (shape.getPlaceholderType() === SlidesApp.PlaceholderType.SUBTITLE) {
      var text = _cleanText(shape.getText().asString().trim());
      if (text) return text;
    }
  }
  return '';
}

function _getBodyLines(slide, resolvedTitle) {
  var skipTypes = [
    SlidesApp.PlaceholderType.TITLE,
    SlidesApp.PlaceholderType.CENTERED_TITLE,
    SlidesApp.PlaceholderType.SUBTITLE
  ];
  var result = [];
  var elements = slide.getPageElements();
  for (var i = 0; i < elements.length; i++) {
    var el = elements[i];
    if (el.getPageElementType() !== SlidesApp.PageElementType.SHAPE) continue;
    var shape = el.asShape();
    if (skipTypes.indexOf(shape.getPlaceholderType()) !== -1) continue;
    var lines = shape.getText().asString().split('\n');
    var shapeLines = lines.map(function(l) { return l.trim(); })
      .filter(function(l) { return l && !_isNoiseLine(l); });
    if (shapeLines.length === 0) continue;
    if (resolvedTitle && _cleanText(shapeLines[0]) === resolvedTitle && shapeLines.length === 1) continue;
    for (var k = 0; k < shapeLines.length; k++) {
      var l = shapeLines[k];
      result.push({ text: _isBulletLine(l) ? _stripBullet(l) : l, isBullet: _isBulletLine(l) });
    }
  }
  return result;
}

function _bodyLinesToText(lines) {
  return lines.map(function(l) { return l.text; }).join('\n');
}

function _getSpeakerNotes(slide) {
  try {
    return _cleanText(slide.getNotes().getSpeakerNotesShape().getText().asString().trim());
  } catch (e) {
    return '';
  }
}
