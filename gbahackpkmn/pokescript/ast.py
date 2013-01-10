

'''
This module contains all elements required to represent a PokeScript program
by means of an AST (Abstract Syntax Tree). Additionally, AST manipulation
scripts are given. Each AST node can be compiled to PokeScript GBA binary code,
or to a text representation for human readability.
'''

from array import array


class NoRewriteChange(Exception):
    '''Exception which indicates that an ASTRewriter has no changes for the node'''
    pass

class ASTRewriter():
    def rewrite(self, ASTNode):
        raise NoRewriteChange()


class ASTNode():
    '''
    AST Node for PokeScript.
    In general, these nodes are fairly simple: a bytecode 
    '''
    
    def encode(self, pointerlist):
        '''
        Encodes the given AST node to representative bytecode.
        Gets a list of varnames to pointers. dict{name: pointer}
        
        Returns an array.array('B') object.
        '''
        raise NotImplementedError()
    
    def text(self):
        '''Returns the AST in the String format.'''
        raise NotImplementedError()

    def linkedPointers(self):
        '''
        Returns a list of pointers this object (and all its children) link to.
        Return format: [(pointer, type)*]
        
        Should only be overwritten if a AST node itself adds new pointers.
        '''
        l = []
        for child in self.childs():
            for ptuple in child.linkedPointers():
                l.append(ptuple)
        return l

    def rewriteASTs(self, rewriter):
        '''
        Replaces child ASTs with an old AST node by a new one.
        Rewriter is a rewriter instance class.
        '''
        raise NotImplementedError()

    def childs(self):
        '''Returns a flattended list of all child AST nodes (all depths).'''
        return []
    


class ASTRoutine(ASTNode):
    '''
    AST Node representing a routine.
    Has a list of AST-nodes representing the instruction calls.
    '''
    def __init__(self, name, subtree):
        self.subtree = subtree
        self.name = name
        
        
    def encode(self, pointerlist):
        bytearray = array('B')
        for astnode in self.subtree:
            bytearray.extend(astnode.encode(pointerlist))
        return bytearray
        
        
    def text(self):
        text = ["#org "+self.name]
        for node in self.subtree:
            text.append(node.text())
        return '\n  '.join(text)
    
    
    def add(self, astnode):
        '''Add an AST childnode to the subtree.'''
        print("ADD to "+repr(self)+": "+repr(astnode))
        self.subtree.append(astnode)
    
    def rewriteASTs(self, rewriter):
        for i in range(0, len(self.subtree)):
            try:
                self.subtree[i] = rewriter.rewrite(self.subtree[i])
            except NoRewriteChange as _:
                pass
        
    def childs(self):
        return self.subtree



class ASTResourceString(ASTNode):
    '''AST Resource Node for PokeString objects.'''
    def __init__(self, name, pokestring):
        self.name = name
        self.string = pokestring


    def text(self):
        strtext = self.string.getText()
        strtext = strtext.replace("\\n", "\\n\n= ")
        strtext = strtext.replace("\p", "\p\n= ")
        strtext = strtext.replace("\l", "\l\n= ")
        return "#text "+self.name + "\n= "+strtext
    
    
    def encode(self, pointerlist):
        return self.string.bytestring()
    
    
    def append(self, text):
        '''Append some text to the text object.'''
        self.string.append(text)


    def rewriteASTs(self, rewriter):
        pass


class ASTResourceMovement(ASTNode):
    '''AST Resource Node for Movement objects.'''
    def __init__(self, name, movement):
        self.name = name
        self.movement = movement
        
        
    def text(self):
        text = "#movement "+self.name+"\n: "
        for move in self.movement.getMovements():
            text += "0x%X "%move
        return text


    def encode(self, pointerlist):
        bytes = array('B')
        for move in self.movement.getMovements():
            bytes.append(move)
        return bytes
    
    
    def rewriteASTs(self, rewriter):
        pass
    
    

class ASTCommand(ASTNode):
    def __init__(self, code, args=[]):
        self.code = code
        self.args = args
    
    
    def text(self):
        #Rewrites code and args to a pokescript line
        command = self.code
        commandsig = command.signature[:]
        
        for argindex in range(0, len(self.args)):
            # note that in the syntax def, these values are counted from $1, not $0!
            sigindex = commandsig.index("$%d"%(argindex+1))
            
            # Rewrite the arg, args can be ASTNodes or literals
            arg = self.args[argindex]
            if isinstance(arg, ASTNode):
                commandsig[sigindex] = arg.text()
            else:
                commandsig[sigindex] = "0x%X"%arg
            
        return ' '.join(commandsig)
    
    
    def encode(self, pointerlist):
        bytes = array('B')
        command = self.code
        commandargs = []
        for arg in self.args:
            #pprint.pprint(arg)
            if isinstance(arg, ASTNode):
                commandargs.append(arg.encode(pointerlist))
            else:
                commandargs.append(arg)
        #print(commandargs)
        bytes.extend(command.compile(*commandargs))
        
        return bytes
    
    def childs(self):
        l = []
        for arg in self.args:
            if isinstance(arg, ASTNode):
                l.append(arg)
        return l


    def rewriteASTs(self, rewriter):
        for i in range(0, len(self.args)):
            if isinstance(self.args[i], ASTNode):
                try:
                    self.args[i] = rewriter.rewrite(self.args[i])
                except:
                    pass



class ASTPointerRef(ASTNode):
    def __init__(self, pointer, pointertype):
        '''
        Represents a raw script pointer.
        Pointertype is of decompiler.DecompileTypes.
        '''
        self.pointer = pointer
        self.pointertype = pointertype
        
    def text(self):
        return "0x%X"%self.pointer
    
    def encode(self, pointerlist):
        if self.pointer != None:
            return 0x08000000 + self.pointer
        print("> Warning: encoding pointer None to 0")
        return 0
    
    def getPointer(self):
        return self.pointer
    
    def linkedPointers(self):
        return [(self.pointer, self.pointertype)]

    def rewriteASTs(self, rewriter):
        pass

        
class ASTRef(ASTNode):
    '''AST node which represents a reference by varname to a resource.'''
    def __init__(self, varname):
        #TODO: Reftype
        self.varname = varname
        
    def text(self):
        return self.varname
    
    def encode(self, pointerlist):
        if not self.varname in pointerlist:
            pointer = None
            #raise Exception("Missing pointer "+self.varname+ " in pointer list: "+repr(pointerlist))
        else:
            pointer = pointerlist[self.varname]
        
        return ASTPointerRef(pointer, None).encode(pointerlist)  #TODO: Fix the none here

    def getRef(self):
        '''Gets the varname to the varname this object points to.'''
        return self.varname

    def setRef(self, varname):
        '''Sets the varname of the varname this object points to.'''
        self.varname = varname

    def rewriteASTs(self, rewriter):
        pass


class ASTByte(ASTNode):
    '''AST node representing a raw byte.'''
    def __init__(self, byte):
        self.byte = byte
        
    def encode(self, pointerlist):
        return array('B', [self.byte])
        
    def text(self):
        return "0x%X" % self.byte
         
    def rewriteASTs(self, rewriter):
        pass