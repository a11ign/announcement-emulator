import controlTypes, speech, speech.speech as ss, config
from speech.commands import *
def flat(seq): return [x if isinstance(x, str) else f'<{type(x).__name__}>' for x in seq]
R = controlTypes.Role; S = controlTypes.State
cases = {
 'heading1': dict(role=R.HEADING, name='Welcome', level=1),
 'link': dict(role=R.LINK, name='Home', states={S.LINKED}),
 'button': dict(role=R.BUTTON, name='Send'),
 'checkbox': dict(role=R.CHECKBOX, name='Agree', states={S.CHECKED}),
 'edit-required': dict(role=R.EDITABLETEXT, name='Name', states={S.REQUIRED, S.EDITABLE}),
}
for k, kw in cases.items():
    try:
        seq = ss.getPropertiesSpeech(reason=controlTypes.OutputReason.FOCUS, **{('states' if a == 'states' else a): v for a, v in kw.items()})
        print(k, '->', flat(seq))
    except Exception as e:
        import traceback; print(k, 'ERR', type(e).__name__, e); traceback.print_exc(limit=-3)
