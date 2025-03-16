mkdir -p ~/.config
mkdir -p ~/.config/pip
echo -e "$PIPCONF" > ~/.config/pip/pip.conf
echo -e "$PYPIRC" > ~/.pypirc
