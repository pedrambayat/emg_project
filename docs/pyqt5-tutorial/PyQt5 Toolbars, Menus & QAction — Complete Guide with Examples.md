---
title: "PyQt5 Toolbars, Menus & QAction — Complete Guide with Examples"
source: "https://www.pythonguis.com/tutorials/pyqt-actions-toolbars-menus/"
author:
  - "[[Martin Fitzpatrick]]"
published: 2019-05-21
created: 2026-04-15
description: "Learn how to create toolbars, menus and keyboard shortcuts in PyQt5 using QAction. Step-by-step tutorial covering QToolBar, QMenu, QStatusBar and QKeySequence with full code examples."
tags:
  - "clippings"
---
Next, we'll look at some of the common user interface elements you've probably seen in many other applications — toolbars and menus. We'll also explore the neat system Qt provides for minimizing the duplication between different UI areas — `QAction`.

In this tutorial, you'll learn how to add **toolbars**, **menus**, **status bars**, and **keyboard shortcuts** to your PyQt5 applications using `QAction`, `QToolBar`, `QMenu`, and `QStatusBar`.

## Basic PyQt5 App Setup

We'll start this tutorial with a simple skeleton application, which we can customize. Save the following code in a file named `app.py` -- this code includes all the imports you'll need for the later steps:

```python
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QKeySequence
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QCheckBox,
    QLabel,
    QMainWindow,
    QStatusBar,
    QToolBar,
)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("My Awesome App")

app = QApplication([])
window = MainWindow()
window.show()
app.exec()
```

This file contains the imports and the basic code that you'll use to complete the examples in this tutorial.

## What Are Toolbars in PyQt5?

One of the most commonly seen user interface elements is the toolbar. Toolbars are bars of icons and/or text used to perform common tasks within an application, for which access via a menu would be cumbersome. They are one of the most common UI features seen in many applications. While some complex applications, particularly in the Microsoft Office suite, have migrated to contextual 'ribbon' interfaces, the standard toolbar is usually sufficient for the majority of applications you will create.

*Standard GUI elements — toolbars provide quick access to common actions*

## Adding a QToolBar to Your PyQt5 Window

Let's start by adding a toolbar to our application.

In Qt, toolbars are created from the `QToolBar` class. To start, you create an instance of the class and then call `addToolbar` on the `QMainWindow`. Passing a string in as the first parameter to `QToolBar` sets the toolbar's name, which will be used to identify the toolbar in the UI:

```python
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("My App")

        label = QLabel("Hello!")
        label.setAlignment(Qt.AlignCenter)

        self.setCentralWidget(label)

        toolbar = QToolBar("My main toolbar")
        self.addToolBar(toolbar)
```

> [!note] Note
> **Run it!** You'll see a thin grey bar at the top of the window. This is your toolbar. Right-click the name to trigger a context menu and toggle the bar off.

![A window with a toolbar.](https://ik.imagekit.io/mfitzp/pythonguis/static/tutorials/qt/actions-toolbars-menus/window-with-toolbar.png?tr=w-600) *A PyQt5 window with a QToolBar added.*

> [!note] Note
> **How can I get my toolbar back?** Unfortunately, once you remove a toolbar, there is now no place to right-click to re-add it. So as a general rule you want to either keep one toolbar un-removeable, or provide an alternative interface in the menus to turn toolbars on and off.

## Using QAction to Add Toolbar Buttons

We should make the toolbar a bit more interesting. We could just add a `QButton` widget, but there is a better approach in Qt that gets you some additional features — and that is via `QAction`. `QAction` is a class that provides a way to describe abstract user interfaces. What this means in English is that you can define multiple interface elements within a single object, unified by the effect that interacting with that element has.

For example, it is common to have functions that are represented in the toolbar but also the menu — think of something like *Edit->Cut* which is present both in the Edit menu but also on the toolbar as a pair of scissors, and also through the keyboard shortcut `Ctrl-X` (`Cmd-X` on Mac).

Without `QAction`, you would have to define this in multiple places. But with `QAction` you can define a single `QAction`, defining the triggered action, and then add this action to both the menu and the toolbar. Each `QAction` has names, status messages, icons, and signals that you can connect to (and much more).

In the code below, you can see this first `QAction` added:

```python
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("My App")

        label = QLabel("Hello!")
        label.setAlignment(Qt.AlignCenter)

        self.setCentralWidget(label)

        toolbar = QToolBar("My main toolbar")
        self.addToolBar(toolbar)

        button_action = QAction("Your button", self)
        button_action.setStatusTip("This is your button")
        button_action.triggered.connect(self.toolbar_button_clicked)
        toolbar.addAction(button_action)

    def toolbar_button_clicked(self, s):
        print("click", s)
```

To start with, we create the function that will accept the signal from the `QAction` so we can see if it is working. Next, we define the `QAction` itself. When creating the instance, we can pass a label for the action and/or an icon. You must also pass in any `QObject` to act as the parent for the action — here we're passing `self` as a reference to our main window. Strangely, for `QAction` the parent element is passed in as the final parameter.

Next, we can opt to set a status tip — this text will be displayed on the status bar once we have one. Finally, we connect the `triggered` signal to the custom function. This signal will fire whenever the `QAction` is *triggered* (or activated).

> [!note] Note
> **Run it!** You should see your button with the label that you have defined. Click on it, and then our custom function will emit "click" and the status of the button.

![Toolbar showing our QAction button.](https://ik.imagekit.io/mfitzp/pythonguis/static/tutorials/qt/actions-toolbars-menus/toolbar-with-qaction-button.png?tr=w-600) *Toolbar showing our `QAction` button.*

> [!note] Note
> **Why is the signal always false?** The signal passed indicates whether the button is *checked*, and since our button is not checkable — just clickable — it is always false. We'll show how to make it checkable shortly.

## Adding a QStatusBar to Display Action Status Tips

Next, we can add a status bar.

We create a status bar object by calling `QStatusBar` to get a new status bar object and then passing this into `setStatusBar`. Since we don't need to change the status bar settings, we can also just pass it in as we create it, in a single line:

```python
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("My Awesome App")

        label = QLabel("Hello!")
        label.setAlignment(Qt.AlignCenter)

        self.setCentralWidget(label)

        toolbar = QToolBar("My main toolbar")
        self.addToolBar(toolbar)

        button_action = QAction("Your button", self)
        button_action.setStatusTip("This is your button")
        button_action.triggered.connect(self.toolbar_button_clicked)
        toolbar.addAction(button_action)

        self.setStatusBar(QStatusBar(self))

    def toolbar_button_clicked(self, s):
        print("click", s)
```

> [!note] Note
> **Run it!** Hover your mouse over the toolbar button, and you will see the status text in the status bar.

![Status bar text is updated as we hover our actions.](https://ik.imagekit.io/mfitzp/pythonguis/static/tutorials/qt/actions-toolbars-menus/statusbar-hover-action.png?tr=w-600) *Status bar text updated as we hover over the action.*

## Making a QAction Checkable (Toggle Button)

Next, we're going to turn our `QAction` toggleable — so clicking will turn it on, and clicking again will turn it off. To do this, we simply call `setCheckable(True)` on the `QAction` object:

```python
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("My App")

        label = QLabel("Hello!")
        label.setAlignment(Qt.AlignCenter)

        self.setCentralWidget(label)

        toolbar = QToolBar("My main toolbar")
        self.addToolBar(toolbar)

        button_action = QAction("Your button", self)
        button_action.setStatusTip("This is your button")
        button_action.triggered.connect(self.toolbar_button_clicked)
        button_action.setCheckable(True)
        toolbar.addAction(button_action)

        self.setStatusBar(QStatusBar(self))

    def toolbar_button_clicked(self, s):
        print("click", s)
```

> [!note] Note
> **Run it!** Click on the button to see it toggle from checked to unchecked state. Note that the custom slot method we create now alternates outputting `True` and `False`.

![The toolbar button toggled on.](https://ik.imagekit.io/mfitzp/pythonguis/static/tutorials/qt/actions-toolbars-menus/toolbar-button-toggled.png?tr=w-600) *The toolbar button toggled on.*

> [!note] Note
> There is also a `toggled` signal, which only emits a signal when the button is toggled. But the effect is identical, so it is mostly pointless.

## Adding Icons to QAction Toolbar Buttons

Things look pretty shabby right now — so let's add an icon to our button. For this, I recommend you download the [fugue icon set](http://p.yusukekamiyamane.com/) by designer Yusuke Kamiyamane. It's a great set of beautiful 16x16 icons that can give your apps a nice professional look. It is freely available with only attribution required when you distribute your application — although I am sure the designer would appreciate some cash too if you have some spare.

![Fugue Icon Set — Yusuke Kamiyamane](https://ik.imagekit.io/mfitzp/pythonguis/static/tutorials/qt/actions-toolbars-menus/fugue-icons.png?tr=w-600) *Fugue Icon Set — Yusuke Kamiyamane*

Select an image from the set (in the examples here, I've selected the file `bug.png`) and copy it into the same folder as your source code.

We can create a `QIcon` object by passing the file name to the class, e.g. `QIcon("bug.png")` -- if you place the file in another folder, you will need a full relative or absolute path to it.

Finally, to add the icon to the `QAction` (and therefore the button) we simply pass it in as the first parameter when creating the `QAction`.

You also need to let the toolbar know how large your icons are. Otherwise, your icon will be surrounded by a lot of padding. You can do this by calling `setIconSize()` with a `QSize` object:

```python
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("My App")

        label = QLabel("Hello!")
        label.setAlignment(Qt.AlignCenter)

        self.setCentralWidget(label)

        toolbar = QToolBar("My main toolbar")
        toolbar.setIconSize(QSize(16,16))
        self.addToolBar(toolbar)

        button_action = QAction(QIcon("bug.png"), "Your button", self)
        button_action.setStatusTip("This is your button")
        button_action.triggered.connect(self.toolbar_button_clicked)
        button_action.setCheckable(True)
        toolbar.addAction(button_action)

        self.setStatusBar(QStatusBar(self))

    def toolbar_button_clicked(self, s):
        print("click", s)
```

> [!note] Note
> **Run it!** The `QAction` is now represented by an icon. Everything should work exactly as it did before.

![Our action button with an icon.](https://ik.imagekit.io/mfitzp/pythonguis/static/tutorials/qt/actions-toolbars-menus/action-button-with-icon.png?tr=w-600) *Our QAction toolbar button with a QIcon.*

## Customizing Toolbar Button Style with setToolButtonStyle

You can control whether the toolbar shows icons, text, or both by using `setToolButtonStyle()`. This slot accepts any of the following flags from the `Qt` namespace:

| PyQt5 flag | Behavior |
| --- | --- |
| `Qt.ToolButtonIconOnly` | Icon only, no text |
| `Qt.ToolButtonTextOnly` | Text only, no icon |
| `Qt.ToolButtonTextBesideIcon` | Icon and text, with text beside the icon |
| `Qt.ToolButtonTextUnderIcon` | Icon and text, with text under the icon |
| `Qt.ToolButtonFollowStyle` | Follow the host desktop style |

The default value is `Qt.ToolButtonFollowStyle`, meaning that your application will default to following the standard/global setting for the desktop on which the application runs. This is generally recommended to make your application feel as *native* as possible.

## Adding Multiple Actions and Widgets to a Toolbar

Finally, we can add a few more bits and bobs to the toolbar. We'll add a second button and a checkbox widget. As mentioned, you can literally put any widget in here, so feel free to go crazy:

```python
from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QCheckBox,
    QLabel,
    QMainWindow,
    QStatusBar,
    QToolBar,
)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("My App")

        label = QLabel("Hello!")
        label.setAlignment(Qt.AlignCenter)

        self.setCentralWidget(label)

        toolbar = QToolBar("My main toolbar")
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(toolbar)

        button_action = QAction(QIcon("bug.png"), "&Your button", self)
        button_action.setStatusTip("This is your button")
        button_action.triggered.connect(self.toolbar_button_clicked)
        button_action.setCheckable(True)
        toolbar.addAction(button_action)

        toolbar.addSeparator()

        button_action2 = QAction(QIcon("bug.png"), "Your &button2", self)
        button_action2.setStatusTip("This is your button2")
        button_action2.triggered.connect(self.toolbar_button_clicked)
        button_action2.setCheckable(True)
        toolbar.addAction(button_action2)

        toolbar.addWidget(QLabel("Hello"))
        toolbar.addWidget(QCheckBox())

        self.setStatusBar(QStatusBar(self))

    def toolbar_button_clicked(self, s):
        print("click", s)

app = QApplication([])
window = MainWindow()
window.show()
app.exec()
```

> [!note] Note
> **Run it!** Now you see multiple buttons and a checkbox.

![Toolbar with an action and two widgets.](https://ik.imagekit.io/mfitzp/pythonguis/static/tutorials/qt/actions-toolbars-menus/toolbar-action-widgets.png?tr=w-600) *PyQt5 toolbar with multiple QAction buttons and custom widgets.*

## Creating Menus in PyQt5 with QMenu

Menus are another standard component of UIs. Typically they are on the top of the window, or the top of a screen on macOS. They allow access to all standard application functions. A few standard menus exist — for example File, Edit, Help. Menus can be nested to create hierarchical trees of functions, and they often support and display keyboard shortcuts for fast access to their functions.

![Standard GUI elements - Menus](https://ik.imagekit.io/mfitzp/pythonguis/static/tutorials/qt/actions-toolbars-menus/menus.png?tr=w-600) *Standard GUI elements — menus provide organized access to application functions*

## Adding a QMenu to Your PyQt5 Application

To create a menu, we create a menubar we call `menuBar()` on the `QMainWindow`. We add a menu to our menu bar by calling `addMenu()`, passing in the name of the menu. I've called it `'&File'`. The ampersand defines a quick key to jump to this menu when pressing Alt.

> [!note] Note
> This won't be visible on macOS. Note that this is different from a keyboard shortcut — we'll cover that shortly.

This is where the power of actions comes into play. We can reuse the already existing `QAction` to add the same function to the menu. To add an action, you call `addAction()` passing in one of our defined actions:

```python
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("My App")

        label = QLabel("Hello!")
        label.setAlignment(Qt.AlignCenter)

        self.setCentralWidget(label)

        toolbar = QToolBar("My main toolbar")
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(toolbar)

        button_action = QAction(QIcon("bug.png"), "&Your button", self)
        button_action.setStatusTip("This is your button")
        button_action.triggered.connect(self.toolbar_button_clicked)
        button_action.setCheckable(True)
        toolbar.addAction(button_action)

        toolbar.addSeparator()

        button_action2 = QAction(QIcon("bug.png"), "Your &button2", self)
        button_action2.setStatusTip("This is your button2")
        button_action2.triggered.connect(self.toolbar_button_clicked)
        button_action2.setCheckable(True)
        toolbar.addAction(button_action2)

        toolbar.addWidget(QLabel("Hello"))
        toolbar.addWidget(QCheckBox())

        self.setStatusBar(QStatusBar(self))

        menu = self.menuBar()

        file_menu = menu.addMenu("&File")
        file_menu.addAction(button_action)

    def toolbar_button_clicked(self, s):
        print("click", s)
```

> [!note] Note
> **Run it!** Click the item in the menu, and you will notice that it is toggleable — it inherits the features of the `QAction`.

![Menu shown on the window -- on macOS this will be at the top of the screen.](https://ik.imagekit.io/mfitzp/pythonguis/static/tutorials/qt/actions-toolbars-menus/menu-shown-on-window.png?tr=w-600) *Menu shown on the window — on macOS this will be at the top of the screen.*

## Adding Separators and Multiple Menu Items

Let's add some more things to the menu. Here, we'll add a separator to the menu, which will appear as a horizontal line in the menu, and then add the second `QAction` we created:

```python
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("My App")

        label = QLabel("Hello!")
        label.setAlignment(Qt.AlignCenter)

        self.setCentralWidget(label)

        toolbar = QToolBar("My main toolbar")
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(toolbar)

        button_action = QAction(QIcon("bug.png"), "&Your button", self)
        button_action.setStatusTip("This is your button")
        button_action.triggered.connect(self.toolbar_button_clicked)
        button_action.setCheckable(True)
        toolbar.addAction(button_action)

        toolbar.addSeparator()

        button_action2 = QAction(QIcon("bug.png"), "Your &button2", self)
        button_action2.setStatusTip("This is your button2")
        button_action2.triggered.connect(self.toolbar_button_clicked)
        button_action2.setCheckable(True)
        toolbar.addAction(button_action2)

        toolbar.addWidget(QLabel("Hello"))
        toolbar.addWidget(QCheckBox())

        self.setStatusBar(QStatusBar(self))

        menu = self.menuBar()

        file_menu = menu.addMenu("&File")
        file_menu.addAction(button_action)
        file_menu.addSeparator()
        file_menu.addAction(button_action2)

    def toolbar_button_clicked(self, s):
        print("click", s)
```

> [!note] Note
> **Run it!** You should see two menu items with a line between them.

![Our actions showing in the menu.](https://ik.imagekit.io/mfitzp/pythonguis/static/tutorials/qt/actions-toolbars-menus/actions-shown-in-menu.png?tr=w-600) *Two QAction items with a separator in the File menu.*

You can also use ampersand to add *accelerator keys* to the menu to allow a single key to be used to jump to a menu item when it is open. Again this doesn't work on macOS.

## Creating Submenus in PyQt5

To add a submenu, you simply create a new menu by calling `addMenu()` on the parent menu. You can then add actions to it as normal. For example:

```python
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("My App")

        label = QLabel("Hello!")
        label.setAlignment(Qt.AlignCenter)

        self.setCentralWidget(label)

        toolbar = QToolBar("My main toolbar")
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(toolbar)

        button_action = QAction(QIcon("bug.png"), "&Your button", self)
        button_action.setStatusTip("This is your button")
        button_action.triggered.connect(self.toolbar_button_clicked)
        button_action.setCheckable(True)
        toolbar.addAction(button_action)

        toolbar.addSeparator()

        button_action2 = QAction(QIcon("bug.png"), "Your &button2", self)
        button_action2.setStatusTip("This is your button2")
        button_action2.triggered.connect(self.toolbar_button_clicked)
        button_action2.setCheckable(True)
        toolbar.addAction(button_action2)

        toolbar.addWidget(QLabel("Hello"))
        toolbar.addWidget(QCheckBox())

        self.setStatusBar(QStatusBar(self))

        menu = self.menuBar()

        file_menu = menu.addMenu("&File")
        file_menu.addAction(button_action)
        file_menu.addSeparator()

        file_submenu = file_menu.addMenu("Submenu")
        file_submenu.addAction(button_action2)

    def toolbar_button_clicked(self, s):
        print("click", s)
```

> [!note] Note
> **Run it!** You will see a nested menu in the *File* menu.

![Submenu nested in the File menu.](https://ik.imagekit.io/mfitzp/pythonguis/static/tutorials/qt/actions-toolbars-menus/submenu-nested-in-file-menu.png?tr=w-600) *Submenu nested in the File menu.*

## Adding Keyboard Shortcuts with QKeySequence

Finally, we'll add a keyboard shortcut to the `QAction`. You define a keyboard shortcut by passing `setKeySequence()` and passing in the key sequence. Any defined key sequences will appear in the menu.

> [!note] Note
> Note that the keyboard shortcut is associated with the `QAction` and will still work whether or not the `QAction` is added to a menu or a toolbar.

Key sequences can be defined in multiple ways - either by passing as text, using key names from the `Qt` namespace, or using the defined key sequences from the `Qt` namespace. Use the latter wherever you can to ensure compliance with the operating system standards.

The completed code, showing the toolbar buttons and menus is shown below:

```python
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon, QKeySequence
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QCheckBox,
    QLabel,
    QMainWindow,
    QStatusBar,
    QToolBar,
)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("My App")

        label = QLabel("Hello!")

        # The \`Qt\` namespace has a lot of attributes to customize
        # widgets. See: http://doc.qt.io/qt-5/qt.html
        label.setAlignment(Qt.AlignCenter)

        # Set the central widget of the Window. Widget will expand
        # to take up all the space in the window by default.
        self.setCentralWidget(label)

        toolbar = QToolBar("My main toolbar")
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(toolbar)

        button_action = QAction(QIcon("bug.png"), "&Your button", self)
        button_action.setStatusTip("This is your button")
        button_action.triggered.connect(self.toolbar_button_clicked)
        button_action.setCheckable(True)
        # You can enter keyboard shortcuts using key names (e.g. Ctrl+p)
        # Qt.namespace identifiers (e.g. Qt.CTRL + Qt.Key_P)
        # or system agnostic identifiers (e.g. QKeySequence.Print)
        button_action.setShortcut(QKeySequence("Ctrl+p"))
        toolbar.addAction(button_action)

        toolbar.addSeparator()

        button_action2 = QAction(QIcon("bug.png"), "Your &button2", self)
        button_action2.setStatusTip("This is your button2")
        button_action2.triggered.connect(self.toolbar_button_clicked)
        button_action2.setCheckable(True)
        toolbar.addAction(button_action2)

        toolbar.addWidget(QLabel("Hello"))
        toolbar.addWidget(QCheckBox())

        self.setStatusBar(QStatusBar(self))

        menu = self.menuBar()

        file_menu = menu.addMenu("&File")
        file_menu.addAction(button_action)

        file_menu.addSeparator()

        file_submenu = file_menu.addMenu("Submenu")

        file_submenu.addAction(button_action2)

    def toolbar_button_clicked(self, s):
        print("click", s)

app = QApplication([])
window = MainWindow()
window.show()
app.exec()
```

## Summary

In this tutorial you've learned how to build PyQt5 applications with toolbars, menus, status bars, and keyboard shortcuts using `QAction`. Here's a quick recap of the key concepts:

- **QToolBar** — creates a toolbar that can hold action buttons and custom widgets
- **QAction** — defines a single action that can be shared across toolbars, menus, and keyboard shortcuts
- **QStatusBar** — displays status tips and messages at the bottom of your window
- **QMenu** — creates menus and submenus in your application's menu bar
- **QKeySequence** — assigns keyboard shortcuts to actions for fast access

The `QAction` system is one of the most powerful features of Qt, allowing you to define an action once and reuse it in multiple places. Experiment with building your own menus using `QAction` and `QMenu`. Try adding different actions, keyboard shortcuts, and submenus to create a complete menu structure for your PyQt5 application.

Mark As Complete

Continue with [PyQt5 Tutorial](https://www.pythonguis.com/tutorials/pyqt-dialogs/ "Continue to next part")

Return to [Create Desktop GUI Applications with PyQt5](https://www.pythonguis.com/pyqt5-tutorial/)

![](https://static.martinfitzpatrick.com/theme/static/images/books/packaging.png)

[Packaging Python Applications with PyInstaller](https://www.pythonguis.com/packaging-book/) *by Martin Fitzpatrick*

This step-by-step guide walks you through packaging your own Python applications from simple examples to complete installers and signed executables.

[More info](https://www.pythonguis.com/packaging-book/) [Get the book](https://secure.pythonguis.com/01hf77hrbf5v8z5kjtwbhmbwjz/)