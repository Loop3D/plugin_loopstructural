"""Manager for storing and retrieving LoopStructural interpolators."""

from typing import Dict, List
import dill as pickle


class InterpolatorManager:
    """Manages a collection of LoopStructural interpolators with unique keys.
    
    This class provides storage, retrieval, and persistence for interpolator
    objects, allowing users to build multiple interpolators and reference them
    by name for later evaluation.
    """

    def __init__(self):
        """Initialize the interpolator manager with an empty storage."""
        self._interpolators: Dict[str, any] = {}

    def add_interpolator(self, name: str, interpolator) -> None:
        """Add or update an interpolator with the given name.
        
        Parameters
        ----------
        name : str
            Unique identifier for the interpolator
        interpolator : any
            The interpolator object to store
            
        Raises
        ------
        ValueError
            If name is empty or None
        """
        if not name or not name.strip():
            raise ValueError("Interpolator name cannot be empty")
        
        self._interpolators[name.strip()] = interpolator

    def get_interpolator(self, name: str):
        """Retrieve an interpolator by name.
        
        Parameters
        ----------
        name : str
            Name of the interpolator to retrieve
            
        Returns
        -------
        any
            The interpolator object, or None if not found
        """
        return self._interpolators.get(name.strip())

    def remove_interpolator(self, name: str) -> bool:
        """Remove an interpolator by name.
        
        Parameters
        ----------
        name : str
            Name of the interpolator to remove
            
        Returns
        -------
        bool
            True if removed, False if not found
        """
        if name.strip() in self._interpolators:
            del self._interpolators[name.strip()]
            return True
        return False

    def list_interpolators(self) -> List[str]:
        """Get a list of all interpolator names.
        
        Returns
        -------
        List[str]
            List of interpolator names
        """
        return list(self._interpolators.keys())

    def has_interpolator(self, name: str) -> bool:
        """Check if an interpolator exists with the given name.
        
        Parameters
        ----------
        name : str
            Name to check
            
        Returns
        -------
        bool
            True if exists, False otherwise
        """
        return name.strip() in self._interpolators

    def clear(self) -> None:
        """Remove all interpolators."""
        self._interpolators.clear()

    def save_interpolator(self, name: str, filepath: str) -> None:
        """Save a specific interpolator to a pickle file.
        
        Parameters
        ----------
        name : str
            Name of the interpolator to save
        filepath : str
            Path where to save the pickle file
            
        Raises
        ------
        ValueError
            If interpolator with given name doesn't exist
        IOError
            If file cannot be written
        """
        interpolator = self.get_interpolator(name)
        if interpolator is None:
            raise ValueError(f"Interpolator '{name}' not found")
        
        with open(filepath, 'wb') as f:
            pickle.dump(interpolator, f)

    def load_interpolator(self, name: str, filepath: str) -> None:
        """Load an interpolator from a pickle file and store it with the given name.
        
        Parameters
        ----------
        name : str
            Name to assign to the loaded interpolator
        filepath : str
            Path to the pickle file
            
        Raises
        ------
        ValueError
            If name is empty
        IOError
            If file cannot be read
        """
        if not name or not name.strip():
            raise ValueError("Interpolator name cannot be empty")
        
        with open(filepath, 'rb') as f:
            interpolator = pickle.load(f)
        
        self.add_interpolator(name, interpolator)

    def count(self) -> int:
        """Get the number of stored interpolators.
        
        Returns
        -------
        int
            Number of interpolators
        """
        return len(self._interpolators)
